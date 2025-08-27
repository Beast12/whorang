"""Home Assistant camera entity integration."""

from typing import Optional

import requests
import structlog

from .config import settings

logger = structlog.get_logger()


class HACameraManager:
    """Manages Home Assistant camera entity integration."""

    def __init__(self):
        # For addon API access, prioritize SUPERVISOR_TOKEN over long-lived token
        self.supervisor_token = settings.supervisor_token or settings.hassio_token
        self.ha_access_token = settings.ha_access_token
        self.base_url = "http://supervisor/core/api"

    def get_available_cameras(self) -> list:
        """Get list of available camera entities from Home Assistant."""
        # For addon API access, use SUPERVISOR_TOKEN first, then long-lived token as fallback
        token = self.supervisor_token or self.ha_access_token
        if not token:
            logger.warning("No Home Assistant token available for camera discovery")
            logger.debug(
                f"supervisor_token: {bool(self.supervisor_token)}, ha_access_token: {bool(self.ha_access_token)}"
            )
            return []

        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            logger.debug(f"Requesting camera entities from: {self.base_url}/states")
            logger.debug(
                f"Using token type: {'supervisor' if self.supervisor_token else 'long-lived'}"
            )

            response = requests.get(
                f"{self.base_url}/states", headers=headers, timeout=10
            )

            logger.debug(f"API response status: {response.status_code}")
            if response.status_code != 200:
                logger.error(f"API response body: {response.text}")

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
        # For addon API access, use SUPERVISOR_TOKEN first, then long-lived token as fallback
        token = self.supervisor_token or self.ha_access_token
        if not token:
            logger.warning("No Home Assistant token available")
            return None

        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Get camera entity state to extract entity_picture
            response = requests.get(
                f"{self.base_url}/states/{entity_id}",
                headers=headers,
                timeout=10,
            )

            if response.status_code == 200:
                entity_data = response.json()
                entity_picture = entity_data.get("attributes", {}).get("entity_picture")

                if entity_picture:
                    # Return the camera proxy URL using entity_picture
                    return f"http://supervisor:8123{entity_picture}"
                else:
                    logger.warning(f"No entity_picture found for {entity_id}")
                    return None

            logger.warning(
                f"Failed to get entity state for {entity_id}: {response.status_code}"
            )
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
