"""Configuration management for the doorbell face recognition addon."""

import os
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Camera configuration
    camera_url: str = os.getenv("CAMERA_URL", "rtsp://192.168.1.100:554/stream")

    # Storage configuration
    storage_path: str = os.getenv("STORAGE_PATH", "/share/doorbell")
    retention_days: int = int(os.getenv("RETENTION_DAYS", "30"))

    # Face recognition settings
    face_confidence_threshold: float = float(
        os.getenv("FACE_CONFIDENCE_THRESHOLD", "0.6")
    )

    # Notification settings
    notification_webhook: Optional[str] = os.getenv("NOTIFICATION_WEBHOOK")

    # Database settings
    database_encryption: bool = (
        os.getenv("DATABASE_ENCRYPTION", "false").lower() == "true"
    )

    # Home Assistant integration
    hassio_token: Optional[str] = os.getenv("HASSIO_TOKEN")
    supervisor_token: Optional[str] = os.getenv("SUPERVISOR_TOKEN")

    # Application settings
    app_version: str = "1.0.5"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

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


# Global settings instance
settings = Settings()
