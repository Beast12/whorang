"""Home Assistant integration module for the doorbell addon."""

import asyncio
from datetime import datetime
from typing import Any, Dict

import structlog

from .config import settings
from .utils import notification_manager

logger = structlog.get_logger()

_PERSON_DETECTED_THRESHOLD_SECS = 30

_ENTITIES = [
    {
        "entity_id": "sensor.doorbell_last_event",
        "name": "Doorbell Last Event",
        "device_class": "timestamp",
        "icon": "mdi:doorbell-video",
        "unit_of_measurement": None,
    },
    {
        "entity_id": "sensor.doorbell_total_events",
        "name": "Doorbell Total Events",
        "device_class": None,
        "icon": "mdi:counter",
        "unit_of_measurement": "events",
    },
    {
        "entity_id": "binary_sensor.doorbell_person_detected",
        "name": "Doorbell Person Detected",
        "device_class": "occupancy",
        "icon": "mdi:motion-sensor",
        "unit_of_measurement": None,
    },
]


class HomeAssistantIntegration:
    """Manages Home Assistant integration and entity registration."""

    def __init__(self):
        self.ha_api = notification_manager.ha_api

    async def initialize(self):
        """Initialize Home Assistant integration."""
        try:
            await self.register_entities()
            await self.update_sensors()
            logger.info("Home Assistant integration initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize Home Assistant integration", error=str(e))

    async def register_entities(self):
        """Register entities with Home Assistant."""
        await asyncio.gather(
            *[self._register_entity(entity) for entity in _ENTITIES],
            return_exceptions=True,
        )
        logger.info("All entities registered with Home Assistant")

    async def _register_entity(self, entity: Dict[str, Any]):
        """Register a single entity with Home Assistant."""
        attributes = {
            "friendly_name": entity["name"],
            "icon": entity["icon"],
            "source": "whorang",
            "version": settings.app_version,
        }
        if entity.get("device_class"):
            attributes["device_class"] = entity["device_class"]
        if entity.get("unit_of_measurement"):
            attributes["unit_of_measurement"] = entity["unit_of_measurement"]

        await self.ha_api.update_sensor(entity["entity_id"], "unknown", attributes)

    async def update_sensors(self):
        """Update all sensor states."""
        try:
            from .database import db

            last_event = db.get_last_event()
            total_events = db.get_event_count()
            last_event_time = last_event.timestamp.isoformat() if last_event else "unknown"

            person_detected = (
                last_event is not None
                and (datetime.now() - last_event.timestamp).total_seconds()
                < _PERSON_DETECTED_THRESHOLD_SECS
            )

            await asyncio.gather(
                self.ha_api.update_sensor(
                    "sensor.doorbell_last_event",
                    last_event_time,
                    {"friendly_name": "Doorbell Last Event", "icon": "mdi:doorbell-video", "device_class": "timestamp"},
                ),
                self.ha_api.update_sensor(
                    "sensor.doorbell_total_events",
                    total_events,
                    {"friendly_name": "Doorbell Total Events", "icon": "mdi:counter", "unit_of_measurement": "events"},
                ),
                self.ha_api.update_sensor(
                    "binary_sensor.doorbell_person_detected",
                    "on" if person_detected else "off",
                    {"friendly_name": "Doorbell Person Detected", "device_class": "occupancy", "icon": "mdi:motion-sensor"},
                ),
            )
            logger.debug("Sensors updated successfully")

        except Exception as e:
            logger.error("Failed to update sensors", error=str(e))

    async def handle_doorbell_ring(self, event_data: Dict[str, Any]):
        """Handle doorbell ring event."""
        try:
            await asyncio.gather(
                self.update_sensors(),
                self.ha_api.fire_event(
                    "doorbell_ring",
                    {
                        "event_id": event_data.get("event_id"),
                        "timestamp": event_data.get("timestamp"),
                        "image_path": event_data.get("image_path"),
                        "ai_message": event_data.get("ai_message"),
                    },
                ),
            )
            logger.info("Doorbell ring event processed", event_id=event_data.get("event_id"))

        except Exception as e:
            logger.error("Failed to handle doorbell ring event", error=str(e))


# Global integration instance
ha_integration = HomeAssistantIntegration()
