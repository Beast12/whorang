"""Configuration management for the doorbell addon."""

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

    # Notification settings
    notification_webhook: Optional[str] = os.getenv("NOTIFICATION_WEBHOOK")

    # Weather integration
    weather_entity: Optional[str] = os.getenv("WEATHER_ENTITY")

    # Face recognition
    face_recognition_enabled: bool = os.getenv("FACE_RECOGNITION_ENABLED", "false").lower() == "true"
    face_recognition_model: str = os.getenv("FACE_RECOGNITION_MODEL", "buffalo_sc")
    face_recognition_threshold: float = float(os.getenv("FACE_RECOGNITION_THRESHOLD", "0.45"))

    # Home Assistant integration
    hassio_token: Optional[str] = os.getenv("HASSIO_TOKEN")
    supervisor_token: Optional[str] = os.getenv("SUPERVISOR_TOKEN")
    ha_access_token: Optional[str] = os.getenv("HA_ACCESS_TOKEN")

    # Application settings
    app_version: ClassVar[str] = "1.0.132"
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
    def config_file_path(self) -> str:
        """Get the configuration file path."""
        return os.path.join(self.storage_path, "config", "settings.json")

    @property
    def persons_path(self) -> str:
        """Get the persons thumbnails directory path."""
        return os.path.join(self.storage_path, "persons")

    @property
    def insightface_models_path(self) -> str:
        """Get the insightface models directory path."""
        return os.path.join(self.storage_path, "insightface_models")

    # Fields persisted to / loaded from the settings JSON file
    _PERSISTED_FIELDS: ClassVar[tuple] = (
        "camera_url",
        "camera_entity",
        "ha_access_token",
        "weather_entity",
        "notification_webhook",
        "retention_days",
        "storage_path",
        "face_recognition_enabled",
        "face_recognition_model",
        "face_recognition_threshold",
    )

    def save_to_file(self):
        """Save current settings to file."""
        try:
            os.makedirs(os.path.dirname(self.config_file_path), exist_ok=True)
            config_data = {field: getattr(self, field) for field in self._PERSISTED_FIELDS}
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
                for field in self._PERSISTED_FIELDS:
                    if field in config_data:
                        setattr(self, field, config_data[field])
        except Exception as e:
            print(f"Error loading settings: {e}")


# Global settings instance
settings = Settings()
# Load saved settings on startup
settings.load_from_file()
