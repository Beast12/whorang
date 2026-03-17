"""Tests for GET /api/settings/notify-services and /api/settings/binary-sensors."""
import os
import sys
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_real_staticfiles_init = None


def _patched_staticfiles_init(self, **kwargs):
    kwargs["check_dir"] = False
    _real_staticfiles_init(self, **kwargs)


def _patch_app_imports():
    global _real_staticfiles_init
    from starlette.staticfiles import StaticFiles
    if _real_staticfiles_init is None:
        _real_staticfiles_init = StaticFiles.__init__
        StaticFiles.__init__ = _patched_staticfiles_init


_patch_app_imports()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    import src.app as app_mod
    mock_ha_integration = MagicMock()
    mock_ha_integration.initialize = AsyncMock()
    with patch.object(app_mod, 'ha_integration', mock_ha_integration), \
         patch.object(app_mod, 'ensure_directories', MagicMock()):
        with TestClient(app_mod.app, raise_server_exceptions=True) as c:
            yield c


def _mock_ha_api_get(return_value):
    """Return an AsyncMock for HomeAssistantAPI._get with a given JSON response."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = return_value
    mock_api = MagicMock()
    mock_api._get = AsyncMock(return_value=mock_resp)
    return mock_api


def test_notify_services_filters_and_classifies(client):
    ha_services_response = [
        {"domain": "notify", "services": {"mobile_app_phone": {}, "tts_kitchen": {}, "pushover": {}}},
        {"domain": "light", "services": {"turn_on": {}}},
    ]
    mock_api = _mock_ha_api_get(ha_services_response)
    with patch('src.app.HomeAssistantAPI', return_value=mock_api):
        resp = client.get("/api/settings/notify-services")
    assert resp.status_code == 200
    svcs = {s["name"]: s for s in resp.json()["services"]}
    assert "notify.mobile_app_phone" in svcs
    assert svcs["notify.mobile_app_phone"]["image_capable"] is True
    assert svcs["notify.tts_kitchen"]["image_capable"] is False
    assert "notify.light" not in svcs


def test_notify_services_returns_empty_on_api_failure(client):
    mock_api = MagicMock()
    mock_api._get = AsyncMock(return_value=None)
    with patch('src.app.HomeAssistantAPI', return_value=mock_api):
        resp = client.get("/api/settings/notify-services")
    assert resp.status_code == 200
    assert resp.json()["services"] == []


def test_binary_sensors_filters_entity_ids(client):
    states = [
        {"entity_id": "binary_sensor.doorbell", "attributes": {"friendly_name": "Doorbell"}},
        {"entity_id": "binary_sensor.motion", "attributes": {}},
        {"entity_id": "sensor.temperature", "attributes": {}},
    ]
    mock_api = _mock_ha_api_get(states)
    with patch('src.app.HomeAssistantAPI', return_value=mock_api):
        resp = client.get("/api/settings/binary-sensors")
    assert resp.status_code == 200
    entities = resp.json()["entities"]
    ids = [e["entity_id"] for e in entities]
    assert "binary_sensor.doorbell" in ids
    assert "binary_sensor.motion" in ids
    assert "sensor.temperature" not in ids


def test_binary_sensors_returns_empty_on_api_failure(client):
    mock_api = MagicMock()
    mock_api._get = AsyncMock(return_value=None)
    with patch('src.app.HomeAssistantAPI', return_value=mock_api):
        resp = client.get("/api/settings/binary-sensors")
    assert resp.status_code == 200
    assert resp.json()["entities"] == []
