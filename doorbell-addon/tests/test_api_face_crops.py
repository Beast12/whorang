"""Tests for face crops API endpoints."""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Patch StaticFiles before importing app
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
    mock_frs.is_ready.return_value = True
    mock_frs.initialize = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.face_recognition_enabled = True
    mock_settings.persons_path = str(tmp_path / "persons")
    mock_settings.face_crops_path = str(tmp_path / "face_crops")
    mock_settings.app_version = "1.0.138"
    mock_settings.storage_path = str(tmp_path)
    mock_ha_integration = MagicMock()
    mock_ha_integration.initialize = AsyncMock()
    mock_ha_integration.handle_doorbell_ring = AsyncMock()
    with patch.object(app_mod, 'db', mock_db), \
         patch.object(app_mod, 'face_recognition_service', mock_frs), \
         patch.object(app_mod, 'settings', mock_settings), \
         patch.object(app_mod, 'ha_integration', mock_ha_integration), \
         patch.object(app_mod, 'ensure_directories', MagicMock()):
        with TestClient(app_mod.app, raise_server_exceptions=True) as c:
            c._mock_db = mock_db
            c._mock_frs = mock_frs
            c._tmp_path = tmp_path
            yield c


def test_get_face_crops_returns_list(client):
    client._mock_db.get_face_crops.return_value = [
        {"id": 1, "event_id": 5, "image_path": "/data/face_crops/5_0.jpg",
         "dismissed": 0, "created_at": "2026-01-01", "event_timestamp": "2026-01-01"}
    ]
    resp = client.get("/api/face-crops")
    assert resp.status_code == 200
    data = resp.json()
    assert "crops" in data
    assert data["crops"][0]["image_path"] == "/api/face-crops/1/image"


def test_get_face_crops_count_only(client):
    client._mock_db.get_face_crop_count.return_value = 3
    resp = client.get("/api/face-crops?count_only=true")
    assert resp.status_code == 200
    assert resp.json() == {"count": 3}


def test_get_face_crops_disabled_returns_empty(client):
    import src.app as app_mod
    app_mod.settings.face_recognition_enabled = False
    try:
        resp = client.get("/api/face-crops")
        assert resp.status_code == 200
        assert resp.json() == {"crops": []}
    finally:
        app_mod.settings.face_recognition_enabled = True


def test_dismiss_face_crop(client):
    client._mock_db.get_face_crop.return_value = {
        "id": 1, "event_id": 5, "image_path": "/data/face_crops/5_0.jpg",
        "dismissed": 0, "created_at": "2026-01-01", "event_timestamp": "2026-01-01"
    }
    resp = client.post("/api/face-crops/1/dismiss")
    assert resp.status_code == 204
    client._mock_db.dismiss_face_crop.assert_called_once_with(1)


def test_dismiss_face_crop_not_found(client):
    client._mock_db.get_face_crop.return_value = None
    resp = client.post("/api/face-crops/99/dismiss")
    assert resp.status_code == 404


def test_assign_face_crop_to_existing_person(client, tmp_path):
    """POST /api/face-crops/{id}/assign with person_id."""
    import numpy as np
    from src.face_recognition_service import FaceResult
    from unittest.mock import patch as _patch
    crop_file = tmp_path / "face_crops" / "5_0.jpg"
    crop_file.parent.mkdir(parents=True, exist_ok=True)
    crop_file.write_bytes(b"fake-image")
    client._mock_db.get_face_crop.return_value = {
        "id": 1, "event_id": 5, "image_path": str(crop_file), "dismissed": 0,
        "created_at": "2026-01-01", "event_timestamp": "2026-01-01"
    }
    client._mock_db.get_person.return_value = {
        "id": 2, "name": "Alice", "thumbnail_path": None
    }
    client._mock_db.add_person_embedding.return_value = 10
    face_result = FaceResult(bbox=(0, 0, 50, 50), embedding=np.array([0.1, 0.2, 0.3]), det_score=0.99)
    client._mock_frs.analyze_image.return_value = [face_result]

    # Mock PIL Image.open and ImageOps to avoid needing a real image file
    mock_img = MagicMock()
    mock_img.width = 100
    mock_img.height = 100
    mock_img.crop.return_value = mock_img
    mock_img.resize.return_value = mock_img
    mock_img.convert.return_value = mock_img

    with _patch("PIL.ImageOps.exif_transpose", return_value=mock_img), \
         _patch("PIL.Image.open", return_value=mock_img), \
         _patch("src.app.os.rename"):
        resp = client.post("/api/face-crops/1/assign", json={"person_id": 2})
    assert resp.status_code == 200
    assert resp.json()["person_id"] == 2


def test_assign_face_crop_both_fields_returns_422(client):
    resp = client.post("/api/face-crops/1/assign", json={"person_id": 2, "name": "Alice"})
    assert resp.status_code == 422


def test_assign_face_crop_neither_field_returns_422(client):
    resp = client.post("/api/face-crops/1/assign", json={})
    assert resp.status_code == 422
