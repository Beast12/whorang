"""Home Assistant camera entity integration."""

from typing import Optional

import requests
import structlog

from .config import settings

logger = structlog.get_logger()


class HACameraManager:
    """Manages Home Assistant camera entity integration."""

    def __init__(self):
        self.hassio_token = settings.hassio_token or settings.supervisor_token
        self.base_url = "http://supervisor/core/api"

    def get_available_cameras(self) -> list:
        """Get list of available camera entities from Home Assistant."""
        if not self.hassio_token:
            logger.warning("No Home Assistant token available")
            return []

        try:
            headers = {
                "Authorization": f"Bearer {self.hassio_token}",
                "Content-Type": "application/json",
            }

            response = requests.get(
                f"{self.base_url}/states", headers=headers, timeout=10
            )
            response.raise_for_status()

            states = response.json()
            cameras = [
                {
                    "entity_id": state["entity_id"],
                    "friendly_name": state["attributes"].get(
                        "friendly_name", state["entity_id"]
                    ),
                    "state": state["state"],
                }
                for state in states
                if state["entity_id"].startswith("camera.")
            ]

            logger.info(f"Found {len(cameras)} camera entities")
            return cameras

        except Exception as e:
            logger.error(f"Failed to get camera entities: {e}")
            return []

    def get_camera_stream_url(self, entity_id: str) -> Optional[str]:
        """Get stream URL for a camera entity."""
        if not self.hassio_token:
            logger.warning("No Home Assistant token available")
            return None

        try:
            headers = {
                "Authorization": f"Bearer {self.hassio_token}",
                "Content-Type": "application/json",
            }

            # Get camera proxy stream URL
            response = requests.post(
                f"{self.base_url}/camera_proxy_stream/{entity_id}",
                headers=headers,
                timeout=10,
            )

            if response.status_code == 200:
                # Return the proxy stream URL
                return f"http://supervisor:8123{response.url}"

            logger.warning(f"Failed to get stream URL for {entity_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to get stream URL for {entity_id}: {e}")
            return None

    def test_camera_connection(self, entity_id: str) -> dict:
        """Test connection to a camera entity."""
        try:
            stream_url = self.get_camera_stream_url(entity_id)
            if not stream_url:
                return {"success": False, "error": "Could not get stream URL"}

            # Test if we can access the stream
            response = requests.head(stream_url, timeout=5)
            if response.status_code == 200:
                return {"success": True, "stream_url": stream_url}
            else:
                return {
                    "success": False,
                    "error": f"Stream not accessible: {response.status_code}",
                }

        except Exception as e:
            return {"success": False, "error": str(e)}


# Global instance
ha_camera_manager = HACameraManager()
