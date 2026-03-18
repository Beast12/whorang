"""Utility functions for the doorbell addon."""

import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

import httpx
import structlog

from .config import settings

logger = structlog.get_logger()

_UNSAFE_FILENAME_RE = re.compile(r'[<>:"/\\|?*]')

_AUDIO_ONLY_PREFIXES = ("tts_", "alexa_media_", "google_")
_IMAGE_CAPABLE_PREFIXES = ("mobile_app_", "telegram_", "html5_")


def classify_notify_service(name: str) -> str:
    """Classify a notify service name (without domain prefix).

    Returns 'image' (rich payload with image URL), 'audio' (message only),
    or 'full' (full payload, HA may ignore unsupported data fields).
    """
    for prefix in _IMAGE_CAPABLE_PREFIXES:
        if name.startswith(prefix):
            return "image"
    for prefix in _AUDIO_ONLY_PREFIXES:
        if name.startswith(prefix):
            return "audio"
    return "full"


class HomeAssistantAPI:
    """Home Assistant API client for integration."""

    def __init__(self):
        self.base_url = "http://supervisor/core/api"
        self.headers = {
            "Authorization": f"Bearer {settings.supervisor_token}",
            "Content-Type": "application/json",
        }

    async def _post(self, path: str, json: Optional[Dict] = None) -> Optional[httpx.Response]:
        """POST to the HA API, returning the response or None on error."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}{path}", headers=self.headers, json=json or {}, timeout=10.0
                )
                response.raise_for_status()
                return response
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response is not None else ""
            logger.error("HA API POST failed", path=path, error=str(e), response_body=body)
            return None
        except Exception as e:
            logger.error("HA API POST failed", path=path, error=str(e))
            return None

    async def _get(self, path: str) -> Optional[httpx.Response]:
        """GET from the HA API, returning the response or None on error."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}{path}", headers=self.headers, timeout=10.0
                )
                response.raise_for_status()
                return response
        except Exception as e:
            logger.error("HA API GET failed", path=path, error=str(e))
            return None

    async def send_notification(self, title: str, message: str, data: Optional[Dict] = None):
        """Send a notification to Home Assistant using the notify service."""
        payload = {"title": title, "message": message, "data": data or {}}
        response = await self._post("/services/notify/notify", payload)
        if response:
            logger.info("Notification sent to Home Assistant", title=title)
        else:
            # Fallback to persistent notification
            await self._post(
                "/services/persistent_notification/create",
                {"title": title, "message": message},
            )

    async def update_sensor(self, entity_id: str, state: Any, attributes: Optional[Dict] = None):
        """Update a sensor state in Home Assistant."""
        response = await self._post(
            f"/states/{entity_id}", {"state": state, "attributes": attributes or {}}
        )
        if response:
            logger.info("Sensor updated", entity_id=entity_id, state=state)

    async def fire_event(self, event_type: str, event_data: Dict):
        """Fire an event in Home Assistant."""
        response = await self._post(f"/events/{event_type}", event_data)
        if response:
            logger.info("Event fired", event_type=event_type)

    async def get_weather_data(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get weather data from Home Assistant entity."""
        if not entity_id:
            return None

        response = await self._get(f"/states/{entity_id}")
        if not response:
            return None

        data = response.json()
        attributes = data.get("attributes", {})
        return {
            "condition": data.get("state"),
            "temperature": float(attributes["temperature"]) if "temperature" in attributes else None,
            "humidity": float(attributes["humidity"]) if "humidity" in attributes else None,
        }

    async def call_llmvision(
        self,
        image_file: str,
        provider: str,
        model: str,
        prompt: str,
        max_tokens: int,
    ) -> tuple:
        """Call llmvision.image_analyzer via the supervisor API.

        Returns (response_text, title). Falls back to (default_message, "Doorbell")
        when the call fails or the response is malformed. Timeout is 10 s (set in _post).
        """
        response = await self._post(
            "/services/llmvision/image_analyzer",
            {
                "return_response": True,
                "provider": provider,
                "model": model,
                "message": prompt,
                "image_file": image_file,
                "max_tokens": max_tokens,
                "temperature": 0.2,
            },
        )
        if not response:
            return settings.default_message, "Doorbell"
        svc = response.json().get("service_response", {})
        text = svc.get("response_text") or settings.default_message
        title = svc.get("title") or "Doorbell"
        return text, title

    async def send_ha_notification(
        self,
        service_name: str,
        message: str,
        title: str,
        image_filename: Optional[str] = None,
    ) -> None:
        """Send a notification to a specific HA notify service.

        Payload is tailored to service type: audio-only services get message only;
        image-capable and unknown services get title + message + optional data.image.
        service_name must be the full name e.g. 'notify.mobile_app_phone'.
        """
        suffix = service_name.removeprefix("notify.")
        kind = classify_notify_service(suffix)
        if kind == "audio":
            payload: Dict = {"message": message}
        else:
            payload = {"title": title, "message": message}
            if image_filename:
                payload["data"] = {
                    "image": f"/local/{image_filename}",
                    "ttl": 0,
                    "priority": "high",
                }
        await self._post(f"/services/notify/{suffix}", payload)


class NotificationManager:
    """Manages notifications for doorbell events."""

    def __init__(self):
        self.ha_api = HomeAssistantAPI()

    async def notify_doorbell_ring(
        self,
        event_id: int,
        image_path: str,
        ai_message: Optional[str] = None,
    ):
        """Send notification when the doorbell rings."""
        import asyncio

        title = "Doorbell Ring"
        message = ai_message or "Someone is at the door"
        data = {
            "image_path": image_path,
            "event_id": event_id,
            "timestamp": datetime.now().isoformat(),
        }

        tasks = [self.ha_api.send_notification(title, message, data)]
        if settings.notification_webhook:
            tasks.append(
                self._send_webhook_notification(
                    {
                        "title": title,
                        "message": message,
                        "event": "doorbell_ring",
                        "event_id": event_id,
                        "image_path": image_path,
                        "ai_message": ai_message,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            )

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_webhook_notification(self, data: Dict):
        """Send notification to external webhook (supports Gotify and generic webhooks)."""
        if not settings.notification_webhook:
            return

        webhook_url = settings.notification_webhook
        try:
            if "/message" in webhook_url:
                payload = {
                    "title": data.get("title", "Doorbell Ring"),
                    "message": data.get("message", "Someone is at the door"),
                    "priority": data.get("priority", 5),
                    "extras": {"client::display": {"contentType": "text/markdown"}, "doorbell": data},
                }
            else:
                payload = data

            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload, timeout=10.0)
                response.raise_for_status()
                logger.info("Webhook notification sent successfully")

        except Exception as e:
            logger.error("Failed to send webhook notification", error=str(e), webhook_url=webhook_url)


def ensure_directories():
    """Ensure all required directories exist."""
    for directory in [
        settings.storage_path,
        settings.images_path,
        os.path.dirname(settings.database_path),
        settings.persons_path,
        settings.face_crops_path,
    ]:
        os.makedirs(directory, exist_ok=True)
        logger.info("Directory ensured", path=directory)


def validate_image_file(file_path: str) -> bool:
    """Validate that a file is a valid image."""
    if not os.path.exists(file_path):
        return False
    return os.path.splitext(file_path)[1].lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}


def get_storage_usage() -> Dict[str, Any]:
    """Get storage usage statistics."""
    try:
        import shutil

        total, used, free = shutil.disk_usage(settings.storage_path)
        return {
            "total_gb": total / (1024**3),
            "used_gb": used / (1024**3),
            "free_gb": free / (1024**3),
            "usage_percent": (used / total) * 100,
        }
    except Exception as e:
        logger.error("Error getting storage usage", error=str(e))
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "usage_percent": 0}


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename for safe filesystem usage."""
    filename = _UNSAFE_FILENAME_RE.sub("_", filename).strip(" .")
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[: 255 - len(ext)] + ext
    return filename


# Placeholder image resources — loaded once
_PLACEHOLDER_SIZE = 60
_placeholder_font = None


def _get_font():
    global _placeholder_font
    if _placeholder_font is None:
        from PIL import ImageFont
        try:
            _placeholder_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
        except (OSError, IOError):
            _placeholder_font = ImageFont.load_default()
    return _placeholder_font


def create_placeholder_image(image_name: str) -> Optional[str]:
    """Create a placeholder image for missing files."""
    try:
        from PIL import Image, ImageDraw

        placeholder_dir = os.path.join(settings.storage_path, "placeholders")
        os.makedirs(placeholder_dir, exist_ok=True)
        placeholder_path = os.path.join(placeholder_dir, f"placeholder_{image_name}")

        if os.path.exists(placeholder_path):
            return placeholder_path

        img = Image.new("RGB", (_PLACEHOLDER_SIZE, _PLACEHOLDER_SIZE), color="#6c757d")
        draw = ImageDraw.Draw(img)
        font = _get_font()
        text = "IMG"
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (_PLACEHOLDER_SIZE - (bbox[2] - bbox[0])) // 2
        y = (_PLACEHOLDER_SIZE - (bbox[3] - bbox[1])) // 2
        draw.text((x, y), text, fill="#ffffff", font=font)
        img.save(placeholder_path, "JPEG")
        return placeholder_path

    except Exception as e:
        logger.error(f"Failed to create placeholder image: {e}")
        return None


# Global notification manager instance
notification_manager = NotificationManager()
