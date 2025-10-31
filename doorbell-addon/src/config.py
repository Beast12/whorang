"""Configuration management for the doorbell face recognition addon."""

import json
import os
from typing import ClassVar, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Camera configuration
    camera_url: str = os.getenv("CAMERA_URL", "rtsp://192.168.1.100:554/stream")
    camera_entity: Optional[str] = os.getenv("CAMERA_ENTITY")

    # Storage configuration
    storage_path: str = os.getenv("STORAGE_PATH", "/share/doorbell")
    retention_days: int = int(os.getenv("RETENTION_DAYS", "30"))

    # Face recognition settings
    face_confidence_threshold: float = float(
        os.getenv("FACE_CONFIDENCE_THRESHOLD", "0.6")
    )

    # Notification settings
    notification_webhook: Optional[str] = os.getenv("NOTIFICATION_WEBHOOK")

    # Weather integration
    weather_entity: Optional[str] = os.getenv("WEATHER_ENTITY")

    # Database settings
    database_encryption: bool = (
        os.getenv("DATABASE_ENCRYPTION", "false").lower() == "true"
    )

    # Home Assistant integration
    hassio_token: Optional[str] = os.getenv("HASSIO_TOKEN")
    supervisor_token: Optional[str] = os.getenv("SUPERVISOR_TOKEN")
    ha_access_token: Optional[str] = os.getenv("HA_ACCESS_TOKEN")

    # Application settings
    app_version: ClassVar[str] = "1.0.89"
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"

    @property
    def database_path(self) -> str:
        """Get the database file path."""
        return os.path.join(self.storage_path, "database", "doorbell.db")

    @property
    def images_path(self) -> str:
        """Get the images directory path."""
        return os.path.join(self.storage_path, "images")

    @property
    def faces_path(self) -> str:
        """Get the faces directory path."""
        return os.path.join(self.storage_path, "faces")

    @property
    def config_file_path(self) -> str:
        """Get the configuration file path."""
        return os.path.join(self.storage_path, "config", "settings.json")

    def save_to_file(self):
        """Save current settings to file."""
        try:
            config_dir = os.path.dirname(self.config_file_path)
            os.makedirs(config_dir, exist_ok=True)

            config_data = {
                "camera_url": self.camera_url,
                "camera_entity": self.camera_entity,
                "face_confidence_threshold": self.face_confidence_threshold,
                "ha_access_token": self.ha_access_token,
                "weather_entity": self.weather_entity,
                "notification_webhook": self.notification_webhook,
                "retention_days": self.retention_days,
                "storage_path": self.storage_path,
            }

            with open(self.config_file_path, "w") as f:
                json.dump(config_data, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def load_from_file(self):
        """Load settings from file if it exists."""
        try:
            if os.path.exists(self.config_file_path):
                with open(self.config_file_path, "r") as f:
                    config_data = json.load(f)

                # Update settings with saved values
                if "camera_url" in config_data:
                    self.camera_url = config_data["camera_url"]
                if "camera_entity" in config_data:
                    self.camera_entity = config_data["camera_entity"]
                if "face_confidence_threshold" in config_data:
                    self.face_confidence_threshold = config_data[
                        "face_confidence_threshold"
                    ]
                if "ha_access_token" in config_data:
                    self.ha_access_token = config_data["ha_access_token"]
                if "weather_entity" in config_data:
                    self.weather_entity = config_data["weather_entity"]
                if "notification_webhook" in config_data:
                    self.notification_webhook = config_data["notification_webhook"]
                if "retention_days" in config_data:
                    self.retention_days = config_data["retention_days"]
                if "storage_path" in config_data:
                    self.storage_path = config_data["storage_path"]
        except Exception as e:
            print(f"Error loading settings: {e}")


# Global settings instance
settings = Settings()
# Load saved settings on startup
settings.load_from_file()
