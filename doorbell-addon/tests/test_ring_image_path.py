"""Tests for ring endpoint — thin handler delegates to run_ring_pipeline."""
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


def test_ring_returns_success_response(client):
    """Ring handler returns all required fields."""
    mock_result = {"event_id": 7, "ai_message": "Hi!", "ai_title": "Doorbell"}
    with patch('src.app.run_ring_pipeline', new=AsyncMock(return_value=mock_result)):
        resp = client.post("/api/doorbell/ring", data={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["event_id"] == 7
    assert body["ai_message"] == "Hi!"
    assert body["ai_title"] == "Doorbell"
    assert "timestamp" in body
    assert body["message"] == "Doorbell ring processed"


def test_ring_passes_image_path_to_pipeline(client):
    """image_path form field is forwarded to run_ring_pipeline."""
    mock_result = {"event_id": 1, "ai_message": "Test", "ai_title": "Doorbell"}
    mock_pipeline = AsyncMock(return_value=mock_result)
    with patch('src.app.run_ring_pipeline', new=mock_pipeline):
        client.post("/api/doorbell/ring", data={"image_path": "/some/path.jpg"})
    mock_pipeline.assert_called_once()
    assert mock_pipeline.call_args.kwargs["image_path"] == "/some/path.jpg"


def test_ring_passes_ai_message_to_pipeline(client):
    """ai_message form field is forwarded to run_ring_pipeline."""
    mock_result = {"event_id": 1, "ai_message": "Custom", "ai_title": "Doorbell"}
    mock_pipeline = AsyncMock(return_value=mock_result)
    with patch('src.app.run_ring_pipeline', new=mock_pipeline):
        client.post("/api/doorbell/ring", data={"ai_message": "Custom"})
    assert mock_pipeline.call_args.kwargs["ai_message"] == "Custom"


def test_ring_pipeline_error_returns_500(client):
    """RuntimeError from pipeline becomes HTTP 500."""
    with patch('src.app.run_ring_pipeline', new=AsyncMock(side_effect=RuntimeError("Camera fail"))):
        resp = client.post("/api/doorbell/ring", data={})
    assert resp.status_code == 500
