"""Tests for ring endpoint using a pre-captured image_path instead of camera capture."""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

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
def client(tmp_path):
    from fastapi.testclient import TestClient
    import src.app as app_mod
    mock_db = MagicMock()
    mock_frs = MagicMock()
    mock_frs.is_ready.return_value = False  # disable face recognition
    mock_frs.initialize = AsyncMock()
    mock_camera = MagicMock()
    mock_settings = MagicMock()
    mock_settings.face_recognition_enabled = False
    mock_settings.images_path = str(tmp_path / "images")
    mock_settings.app_version = "1.0.138"
    mock_settings.storage_path = str(tmp_path)
    mock_settings.weather_entity = None
    mock_ha_integration = MagicMock()
    mock_ha_integration.initialize = AsyncMock()
    mock_ha_integration.handle_doorbell_ring = AsyncMock()
    mock_db.add_doorbell_event.return_value = MagicMock(
        id=1, image_path=str(tmp_path / "images" / "doorbell_test.jpg")
    )
    with patch.object(app_mod, 'db', mock_db), \
         patch.object(app_mod, 'face_recognition_service', mock_frs), \
         patch.object(app_mod, 'settings', mock_settings), \
         patch.object(app_mod, 'ha_integration', mock_ha_integration), \
         patch.object(app_mod, 'ha_camera_manager', mock_camera), \
         patch.object(app_mod, 'ensure_directories', MagicMock()):
        with TestClient(app_mod.app, raise_server_exceptions=True) as c:
            c._mock_db = mock_db
            c._mock_camera = mock_camera
            c._tmp_path = tmp_path
            yield c


def test_ring_with_image_path_skips_camera_capture(client, tmp_path):
    """When image_path is provided and exists, camera capture must NOT be called."""
    # Create a real image file simulating HA's snapshot
    snapshot = tmp_path / "doorbell_snapshot_123.jpg"
    snapshot.write_bytes(b"JFIF-fake-image-data")

    resp = client.post("/api/doorbell/ring", data={
        "ai_message": "Hello there",
        "image_path": str(snapshot),
    })

    assert resp.status_code == 200
    client._mock_camera.capture_image.assert_not_called()


def test_ring_with_image_path_copies_file_to_storage(client, tmp_path):
    """When image_path is provided, the file is copied into addon image storage."""
    import src.app as app_mod

    snapshot = tmp_path / "doorbell_snapshot_456.jpg"
    snapshot.write_bytes(b"JFIF-fake-image-data")

    os.makedirs(app_mod.settings.images_path, exist_ok=True)
    resp = client.post("/api/doorbell/ring", data={
        "image_path": str(snapshot),
    })

    assert resp.status_code == 200
    # The stored path passed to db.add_doorbell_event must be inside images_path
    call_kwargs = client._mock_db.add_doorbell_event.call_args
    stored_path = call_kwargs.kwargs.get("image_path") or call_kwargs.args[0]
    assert stored_path.startswith(app_mod.settings.images_path)


def test_ring_without_image_path_falls_back_to_camera(client, tmp_path):
    """When no image_path is given, camera capture is used as before."""
    import src.app as app_mod
    os.makedirs(app_mod.settings.images_path, exist_ok=True)

    # Make capture_image write a file and return True
    def fake_capture(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(b"JFIF-camera-data")
        return True

    client._mock_camera.capture_image.side_effect = fake_capture

    resp = client.post("/api/doorbell/ring", data={"ai_message": "test"})

    assert resp.status_code == 200
    client._mock_camera.capture_image.assert_called_once()


def test_ring_with_nonexistent_image_path_falls_back_to_camera(client, tmp_path):
    """When image_path is given but file is missing, camera capture is used."""
    import src.app as app_mod
    os.makedirs(app_mod.settings.images_path, exist_ok=True)

    def fake_capture(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(b"JFIF-camera-data")
        return True

    client._mock_camera.capture_image.side_effect = fake_capture

    resp = client.post("/api/doorbell/ring", data={
        "image_path": "/nonexistent/path/snapshot.jpg",
    })

    assert resp.status_code == 200
    client._mock_camera.capture_image.assert_called_once()
