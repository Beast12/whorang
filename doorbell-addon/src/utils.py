"""Utility functions for the doorbell face recognition addon."""

import os
from datetime import datetime
from typing import Any, Dict, Optional

import httpx
import structlog

from .config import settings

# Configure structured logging
logger = structlog.get_logger()


class HomeAssistantAPI:
    """Home Assistant API client for integration."""

    def __init__(self):
        self.base_url = "http://supervisor/core/api"
        self.headers = {
            "Authorization": f"Bearer {settings.supervisor_token}",
            "Content-Type": "application/json",
        }

    async def send_notification(
        self, title: str, message: str, data: Optional[Dict] = None
    ):
        """Send a notification to Home Assistant."""
        try:
            payload = {"title": title, "message": message, "data": data or {}}

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/services/persistent_notification/create",
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                logger.info("Notification sent to Home Assistant", title=title)

        except Exception as e:
            logger.error("Failed to send notification", error=str(e))

    async def update_sensor(
        self, entity_id: str, state: Any, attributes: Optional[Dict] = None
    ):
        """Update a sensor state in Home Assistant."""
        try:
            payload = {"state": state, "attributes": attributes or {}}

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/states/{entity_id}",
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                logger.info("Sensor updated", entity_id=entity_id, state=state)

        except Exception as e:
            logger.error(
                "Failed to update sensor",
                entity_id=entity_id,
                error=str(e),
            )

    async def fire_event(self, event_type: str, event_data: Dict):
        """Fire an event in Home Assistant."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/events/{event_type}",
                    headers=self.headers,
                    json=event_data,
                )
                response.raise_for_status()
                logger.info("Event fired", event_type=event_type)

        except Exception as e:
            logger.error(
                "Failed to fire event",
                event_type=event_type,
                error=str(e),
            )


class NotificationManager:
    """Manages notifications for doorbell events."""

    def __init__(self):
        self.ha_api = HomeAssistantAPI()

    async def notify_face_detected(
        self,
        person_name: str,
        confidence: float,
        image_path: str,
        is_known: bool = True,
    ):
        """Send notification when a face is detected."""
        if is_known:
            title = f"Known Person Detected: {person_name}"
            message = f"{person_name} is at the door (confidence: {confidence:.2f})"
        else:
            title = "Unknown Person Detected"
            message = "An unknown person is at the door"

        # Send Home Assistant notification
        await self.ha_api.send_notification(
            title=title,
            message=message,
            data={
                "image_path": image_path,
                "person_name": person_name,
                "confidence": confidence,
                "is_known": is_known,
                "timestamp": datetime.now().isoformat(),
            },
        )

        # Fire custom event
        await self.ha_api.fire_event(
            "doorbell_face_detected",
            {
                "person_name": person_name,
                "confidence": confidence,
                "is_known": is_known,
                "image_path": image_path,
                "timestamp": datetime.now().isoformat(),
            },
        )

        # Send webhook notification if configured
        if settings.notification_webhook:
            await self._send_webhook_notification(
                {
                    "event": "face_detected",
                    "person_name": person_name,
                    "confidence": confidence,
                    "is_known": is_known,
                    "image_path": image_path,
                    "timestamp": datetime.now().isoformat(),
                }
            )

    async def _send_webhook_notification(self, data: Dict):
        """Send webhook notification."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.notification_webhook, json=data, timeout=10.0
                )
                response.raise_for_status()
                logger.info("Webhook notification sent")

        except Exception as e:
            logger.error("Failed to send webhook notification", error=str(e))


def ensure_directories():
    """Ensure all required directories exist."""
    directories = [
        settings.storage_path,
        settings.images_path,
        settings.faces_path,
        os.path.dirname(settings.database_path),
    ]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info("Directory ensured", path=directory)


def cleanup_temp_files():
    """Clean up temporary files."""
    temp_dirs = ["/tmp", "/var/tmp"]

    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            try:
                for filename in os.listdir(temp_dir):
                    if filename.startswith("doorbell_") and filename.endswith(".jpg"):
                        file_path = os.path.join(temp_dir, filename)
                        if os.path.getmtime(file_path) < (
                            datetime.now().timestamp() - 3600
                        ):  # 1 hour old
                            os.remove(file_path)
                            logger.info("Cleaned up temp file", path=file_path)
            except Exception as e:
                logger.error(
                    "Error cleaning temp files",
                    directory=temp_dir,
                    error=str(e),
                )


def validate_image_file(file_path: str) -> bool:
    """Validate that a file is a valid image."""
    if not os.path.exists(file_path):
        return False

    valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
    file_ext = os.path.splitext(file_path)[1].lower()

    return file_ext in valid_extensions


def get_file_size_mb(file_path: str) -> float:
    """Get file size in megabytes."""
    if not os.path.exists(file_path):
        return 0.0

    size_bytes = os.path.getsize(file_path)
    return size_bytes / (1024 * 1024)


def format_confidence(confidence: float) -> str:
    """Format confidence as a percentage string."""
    return f"{confidence * 100:.1f}%"


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
    import re

    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)

    # Remove leading/trailing spaces and dots
    filename = filename.strip(" .")

    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[: 255 - len(ext)] + ext

    return filename


def create_placeholder_image(image_name: str) -> Optional[str]:
    """Create a placeholder image for missing files."""
    try:
        import os

        from PIL import Image, ImageDraw, ImageFont

        # Create placeholder directory if it doesn't exist
        placeholder_dir = os.path.join(settings.storage_path, "placeholders")
        os.makedirs(placeholder_dir, exist_ok=True)

        placeholder_path = os.path.join(placeholder_dir, f"placeholder_{image_name}")

        # Don't recreate if it already exists
        if os.path.exists(placeholder_path):
            return placeholder_path

        # Create a simple placeholder image (60x60 to match thumbnail size)
        img = Image.new("RGB", (60, 60), color="#6c757d")
        draw = ImageDraw.Draw(img)

        # Try to use a font, fallback to default if not available
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10
            )
        except (OSError, IOError):
            font = ImageFont.load_default()

        # Draw camera icon using text
        text = "📷"
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            x = (60 - text_width) // 2
            y = (60 - text_height) // 2

            draw.text((x, y), text, fill="#ffffff", font=font)
        except Exception:
            # Fallback to simple text if emoji doesn't work
            text = "IMG"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            x = (60 - text_width) // 2
            y = (60 - text_height) // 2

            draw.text((x, y), text, fill="#ffffff", font=font)

        # Save placeholder
        img.save(placeholder_path, "JPEG")
        return placeholder_path

    except Exception as e:
        logger.error(f"Failed to create placeholder image: {e}")
        return None


# Global notification manager instance
notification_manager = NotificationManager()
