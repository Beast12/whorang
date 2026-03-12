"""Home Assistant camera entity integration."""

import os
import subprocess
from typing import Dict, Optional

import requests
import structlog

from .config import settings

logger = structlog.get_logger()

_HTTP_TIMEOUT = 10
_FFMPEG_TIMEOUT = 15


class HACameraManager:
    """Manages Home Assistant camera entity integration."""

    def __init__(self):
        self.supervisor_token = settings.supervisor_token or settings.hassio_token
        self.ha_access_token = settings.ha_access_token
        self.base_url = "http://supervisor/core/api"

    def _get_token(self) -> Optional[str]:
        return self.supervisor_token or self.ha_access_token

    def _get_headers(self) -> Optional[Dict[str, str]]:
        token = self._get_token()
        if not token:
            return None
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def get_available_cameras(self) -> list:
        """Get list of available camera entities from Home Assistant."""
        headers = self._get_headers()
        if not headers:
            logger.warning("No Home Assistant token available for camera discovery")
            return []

        try:
            response = requests.get(
                f"{self.base_url}/states", headers=headers, timeout=_HTTP_TIMEOUT
            )
            response.raise_for_status()

            return [
                {
                    "entity_id": state["entity_id"],
                    "friendly_name": state["attributes"].get(
                        "friendly_name", state["entity_id"]
                    ),
                    "state": state["state"],
                }
                for state in response.json()
                if state["entity_id"].startswith("camera.")
            ]

        except Exception as e:
            logger.error(f"Failed to get camera entities: {e}")
            return []

    def get_camera_stream_url(self, entity_id: str) -> Optional[str]:
        """Get stream URL for a camera entity."""
        headers = self._get_headers()
        if not headers:
            logger.warning("No Home Assistant token available")
            return None

        try:
            response = requests.get(
                f"{self.base_url}/states/{entity_id}",
                headers=headers,
                timeout=_HTTP_TIMEOUT,
            )

            if response.status_code == 200:
                entity_picture = response.json().get("attributes", {}).get(
                    "entity_picture"
                )
                if entity_picture:
                    return f"http://homeassistant:8123{entity_picture}"
                logger.warning(f"No entity_picture found for {entity_id}")

            return None

        except Exception as e:
            logger.error(f"Failed to get stream URL for {entity_id}: {e}")
            return None

    def capture_image(self, destination_path: str) -> bool:
        """Capture a single frame from the configured camera source."""
        try:
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)

            if settings.camera_entity:
                headers = self._get_headers()
                if not headers:
                    logger.error("No token available for camera entity capture")
                    return False

                response = requests.get(
                    f"{self.base_url}/camera_proxy/{settings.camera_entity}",
                    headers=headers,
                    timeout=_HTTP_TIMEOUT,
                    stream=True,
                )
                if response.status_code == 200:
                    with open(destination_path, "wb") as f:
                        f.write(response.content)
                    logger.info("Image captured from HA camera entity", entity=settings.camera_entity)
                    return True
                logger.error("Failed to capture from HA camera entity", status=response.status_code)
                return False

            camera_url = settings.camera_url
            if camera_url.startswith(("http://", "https://")):
                response = requests.get(camera_url, timeout=_HTTP_TIMEOUT, stream=True)
                if response.status_code == 200:
                    with open(destination_path, "wb") as f:
                        f.write(response.content)
                    logger.info("Image captured from HTTP camera URL")
                    return True
                logger.error("Failed to capture from HTTP URL", status=response.status_code)
                return False

            if camera_url.startswith("rtsp://"):
                result = subprocess.run(
                    ["ffmpeg", "-y", "-i", camera_url, "-frames:v", "1", "-q:v", "2", destination_path],
                    capture_output=True,
                    timeout=_FFMPEG_TIMEOUT,
                )
                if result.returncode == 0 and os.path.exists(destination_path):
                    logger.info("Image captured from RTSP stream")
                    return True
                logger.error("ffmpeg capture failed", stderr=result.stderr.decode(errors="ignore"))
                return False

            logger.error("No camera source configured")
            return False

        except Exception as e:
            logger.error(f"Failed to capture image: {e}")
            return False

    def test_camera_connection(self, entity_id: str) -> dict:
        """Test connection to a camera entity."""
        try:
            stream_url = self.get_camera_stream_url(entity_id)
            if not stream_url:
                return {"success": False, "error": "Could not get stream URL"}

            response = requests.get(stream_url, timeout=5, stream=True)
            if response.status_code == 200:
                return {"success": True, "stream_url": stream_url}
            return {"success": False, "error": f"Stream not accessible: {response.status_code}"}

        except Exception as e:
            return {"success": False, "error": str(e)}


# Global instance
ha_camera_manager = HACameraManager()
