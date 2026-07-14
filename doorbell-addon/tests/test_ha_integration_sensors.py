"""Tests for HomeAssistantIntegration.update_sensors() timestamp handling."""
import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ha_integration import HomeAssistantIntegration  # noqa: E402


def _make_event(ts):
    event = MagicMock()
    event.timestamp = ts
    event.id = 1
    event.ai_message = "Someone is at the door"
    event.weather_condition = None
    event.weather_temperature = None
    event.face_data = None
    return event


@pytest.fixture
def integration():
    obj = HomeAssistantIntegration()
    obj.ha_api = MagicMock()
    obj.ha_api.update_sensor = AsyncMock()
    return obj


@pytest.mark.asyncio
async def test_last_event_sensor_state_is_utc_aware_iso8601(integration):
    """sensor.doorbell_last_event has device_class=timestamp, which HA's REST
    API requires to be a UTC-offset ISO 8601 string (see HA's own /api/states
    examples, e.g. sun.sun's next_rising: "...+00:00"). Sending a naive string
    (no offset) is a contract violation Home Assistant misinterprets, causing
    the sensor to display the wrong time (regression: "Doorbell Last Event"
    showing hours off from the real event time)."""
    naive_local = datetime(2026, 7, 14, 13, 24, 24)  # naive, but genuinely local wall-clock time
    event = _make_event(naive_local)

    mock_db = MagicMock()
    mock_db.get_last_event.return_value = event
    mock_db.get_event_count.return_value = 5
    mock_db.get_today_event_count.return_value = 1

    with patch('src.database.db', mock_db):
        await integration.update_sensors()

    calls = {c.args[0]: c.args[1] for c in integration.ha_api.update_sensor.call_args_list}
    state = calls["sensor.doorbell_last_event"]

    parsed = datetime.fromisoformat(state)
    assert parsed.tzinfo is not None
    assert parsed.astimezone(timezone.utc) == naive_local.astimezone(timezone.utc)


@pytest.mark.asyncio
async def test_no_last_event_reports_unknown(integration):
    mock_db = MagicMock()
    mock_db.get_last_event.return_value = None
    mock_db.get_event_count.return_value = 0
    mock_db.get_today_event_count.return_value = 0

    with patch('src.database.db', mock_db):
        await integration.update_sensors()

    calls = {c.args[0]: c.args[1] for c in integration.ha_api.update_sensor.call_args_list}
    assert calls["sensor.doorbell_last_event"] == "unknown"
