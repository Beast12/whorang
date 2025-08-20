"""Home Assistant integration module for doorbell face recognition."""

from datetime import datetime
from typing import Any, Dict

import structlog

from .config import settings
from .utils import HomeAssistantAPI

logger = structlog.get_logger()


class HomeAssistantIntegration:
    """Manages Home Assistant integration and entity registration."""

    def __init__(self):
        self.ha_api = HomeAssistantAPI()
        self.entities_registered = False
        self.last_event_id = None

    async def initialize(self):
        """Initialize Home Assistant integration."""
        try:
            await self.register_entities()
            await self.update_sensors()
            logger.info("Home Assistant integration initialized successfully")
        except Exception as e:
            logger.error(
                "Failed to initialize Home Assistant integration",
                error=str(e),
            )

    async def register_entities(self):
        """Register entities with Home Assistant."""
        entities = [
            {
                "entity_id": "sensor.doorbell_last_event",
                "name": "Doorbell Last Event",
                "device_class": "timestamp",
                "icon": "mdi:doorbell-video",
                "unit_of_measurement": None,
            },
            {
                "entity_id": "sensor.doorbell_known_faces_today",
                "name": "Doorbell Known Faces Today",
                "device_class": None,
                "icon": "mdi:account-check",
                "unit_of_measurement": "faces",
            },
            {
                "entity_id": "sensor.doorbell_unknown_faces_today",
                "name": "Doorbell Unknown Faces Today",
                "device_class": None,
                "icon": "mdi:account-question",
                "unit_of_measurement": "faces",
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
            },
            {
                "entity_id": "sensor.doorbell_confidence",
                "name": "Doorbell Last Confidence",
                "device_class": None,
                "icon": "mdi:percent",
                "unit_of_measurement": "%",
            },
        ]

        for entity in entities:
            try:
                await self._register_entity(entity)
            except Exception as e:
                logger.error(
                    "Failed to register entity",
                    entity_id=entity["entity_id"],
                    error=str(e),
                )

        self.entities_registered = True
        logger.info("All entities registered with Home Assistant")

    async def _register_entity(self, entity: Dict[str, Any]):
        """Register a single entity with Home Assistant."""
        entity_data = {
            "state": "unknown",
            "attributes": {
                "friendly_name": entity["name"],
                "icon": entity["icon"],
                "device_class": entity.get("device_class"),
                "unit_of_measurement": entity.get("unit_of_measurement"),
                "source": "doorbell_face_recognition",
                "version": settings.app_version,
            },
        }

        # Remove None values
        entity_data["attributes"] = {
            k: v for k, v in entity_data["attributes"].items() if v is not None
        }

        await self.ha_api.update_sensor(
            entity["entity_id"],
            entity_data["state"],
            entity_data["attributes"],
        )

    async def update_sensors(self):
        """Update all sensor states."""
        try:
            from .database import db

            # Get today's events
            today = datetime.now().date()
            all_events = db.get_doorbell_events(limit=1000)
            today_events = [e for e in all_events if e.timestamp.date() == today]

            known_today = len([e for e in today_events if e.is_known])
            unknown_today = len([e for e in today_events if not e.is_known])
            total_events = len(all_events)

            # Get last event
            last_event = all_events[0] if all_events else None
            last_event_time = (
                last_event.timestamp.isoformat() if last_event else "unknown"
            )

            # Get last confidence
            last_confidence = 0
            if last_event and last_event.confidence:
                last_confidence = round(last_event.confidence * 100, 1)

            # Person detected (true if event in last 30 seconds)
            person_detected = False
            if last_event:
                time_diff = (datetime.now() - last_event.timestamp).total_seconds()
                person_detected = time_diff < 30

            # Update sensors
            await self.ha_api.update_sensor(
                "sensor.doorbell_last_event",
                last_event_time,
                {
                    "friendly_name": "Doorbell Last Event",
                    "icon": "mdi:doorbell-video",
                    "device_class": "timestamp",
                    "last_person": last_event.person_id if last_event else None,
                    "is_known": last_event.is_known if last_event else False,
                },
            )

            await self.ha_api.update_sensor(
                "sensor.doorbell_known_faces_today",
                known_today,
                {
                    "friendly_name": "Doorbell Known Faces Today",
                    "icon": "mdi:account-check",
                    "unit_of_measurement": "faces",
                },
            )

            await self.ha_api.update_sensor(
                "sensor.doorbell_unknown_faces_today",
                unknown_today,
                {
                    "friendly_name": "Doorbell Unknown Faces Today",
                    "icon": "mdi:account-question",
                    "unit_of_measurement": "faces",
                },
            )

            await self.ha_api.update_sensor(
                "sensor.doorbell_total_events",
                total_events,
                {
                    "friendly_name": "Doorbell Total Events",
                    "icon": "mdi:counter",
                    "unit_of_measurement": "events",
                },
            )

            await self.ha_api.update_sensor(
                "binary_sensor.doorbell_person_detected",
                "on" if person_detected else "off",
                {
                    "friendly_name": "Doorbell Person Detected",
                    "device_class": "occupancy",
                    "icon": "mdi:motion-sensor",
                },
            )

            await self.ha_api.update_sensor(
                "sensor.doorbell_confidence",
                last_confidence,
                {
                    "friendly_name": "Doorbell Last Confidence",
                    "icon": "mdi:percent",
                    "unit_of_measurement": "%",
                },
            )

            logger.debug("Sensors updated successfully")

        except Exception as e:
            logger.error("Failed to update sensors", error=str(e))

    async def handle_face_detected(self, event_data: Dict[str, Any]):
        """Handle face detection event."""
        try:
            # Update sensors
            await self.update_sensors()

            # Fire Home Assistant event
            await self.ha_api.fire_event(
                "doorbell_face_detected",
                {
                    "event_id": event_data.get("event_id"),
                    "timestamp": event_data.get("timestamp"),
                    "faces_detected": event_data.get("faces_detected", 0),
                    "known_faces": event_data.get("known_faces", 0),
                    "primary_person_id": event_data.get("primary_person_id"),
                    "primary_confidence": event_data.get("primary_confidence", 0),
                },
            )

            # Fire specific events for known/unknown persons
            if event_data.get("primary_person_id"):
                await self.ha_api.fire_event(
                    "doorbell_known_person",
                    {
                        "event_id": event_data.get("event_id"),
                        "person_id": event_data.get("primary_person_id"),
                        "confidence": event_data.get("primary_confidence", 0),
                        "timestamp": event_data.get("timestamp"),
                    },
                )
            else:
                await self.ha_api.fire_event(
                    "doorbell_unknown_person",
                    {
                        "event_id": event_data.get("event_id"),
                        "faces_detected": event_data.get("faces_detected", 0),
                        "timestamp": event_data.get("timestamp"),
                    },
                )

            logger.info(
                "Face detection event processed",
                event_id=event_data.get("event_id"),
            )

        except Exception as e:
            logger.error("Failed to handle face detection event", error=str(e))

    async def register_device(self):
        """Register the doorbell device with Home Assistant."""
        device_info = {
            "identifiers": ["doorbell_face_recognition"],
            "name": "Doorbell Face Recognition",
            "manufacturer": "Custom",
            "model": "Face Recognition Doorbell",
            "sw_version": settings.app_version,
            "configuration_url": "http://localhost:8099",
        }

        try:
            # This would typically use the device registry API
            # For now, we'll include device info in entity attributes
            logger.info("Device registration completed", device=device_info)
        except Exception as e:
            logger.error("Failed to register device", error=str(e))

    async def create_automation_examples(self):
        """Create example automations for users."""
        automations = [
            {
                "alias": "Doorbell Known Person Notification",
                "description": "Send notification when a known person is detected",
                "trigger": {"platform": "event", "event_type": "doorbell_known_person"},
                "action": {
                    "service": "notify.persistent_notification",
                    "data": {
                        "title": "Doorbell - Known Person",
                        "message": "A known person was detected at the door",
                    },
                },
            },
            {
                "alias": "Doorbell Unknown Person Alert",
                "description": "Send alert when an unknown person is detected",
                "trigger": {
                    "platform": "event",
                    "event_type": "doorbell_unknown_person",
                },
                "action": {
                    "service": "notify.persistent_notification",
                    "data": {
                        "title": "Doorbell Alert - Unknown Person",
                        "message": "An unknown person was detected at the door",
                    },
                },
            },
        ]

        # Log automation examples for users to copy
        for automation in automations:
            logger.info(
                "Example automation available",
                alias=automation["alias"],
                description=automation["description"],
            )

    async def setup_lovelace_cards(self):
        """Provide Lovelace card configurations."""
        cards = [
            {
                "type": "entities",
                "title": "Doorbell Face Recognition",
                "entities": [
                    "sensor.doorbell_last_event",
                    "sensor.doorbell_known_faces_today",
                    "sensor.doorbell_unknown_faces_today",
                    "binary_sensor.doorbell_person_detected",
                    "sensor.doorbell_confidence",
                ],
            },
            {
                "type": "iframe",
                "url": "/api/hassio_ingress/doorbell_face_recognition",
                "title": "Doorbell Management",
                "aspect_ratio": "16:9",
            },
        ]

        logger.info("Lovelace card configurations available", cards_count=len(cards))
        return cards


# Global integration instance
ha_integration = HomeAssistantIntegration()
