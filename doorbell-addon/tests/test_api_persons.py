"""Tests for persons API endpoints."""
import os
import io
import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Patch StaticFiles and Jinja2Templates before importing app so that
# /app/web/static and /app/web/templates don't need to exist on disk.
_real_staticfiles_init = None
_real_templates_init = None


def _patched_staticfiles_init(self, **kwargs):
    kwargs["check_dir"] = False
    _real_staticfiles_init(self, **kwargs)


def _patch_app_imports():
    """Monkey-patch StaticFiles to skip directory check."""
    global _real_staticfiles_init, _real_templates_init
    from starlette.staticfiles import StaticFiles
    if _real_staticfiles_init is None:
        _real_staticfiles_init = StaticFiles.__init__
        StaticFiles.__init__ = _patched_staticfiles_init


_patch_app_imports()


@pytest.fixture
def client(tmp_path):
    """Create a test client with mocked dependencies."""
    from fastapi.testclient import TestClient
    import src.app as app_mod
    # Patch db and face_recognition_service at module level
    import sqlite3
    _db_path = str(tmp_path / "test.db")
    with sqlite3.connect(_db_path) as _conn:
        _conn.execute(
            "CREATE TABLE IF NOT EXISTS known_persons "
            "(id INTEGER PRIMARY KEY, name TEXT, thumbnail_path TEXT)"
        )
        _conn.execute(
            "INSERT INTO known_persons (id, name) VALUES (1, 'Alice')"
        )
        _conn.commit()
    mock_db = MagicMock()
    mock_db.db_path = _db_path
    mock_frs = MagicMock()
    mock_frs.is_ready.return_value = True
    mock_settings = MagicMock()
    mock_settings.face_recognition_enabled = True
    mock_settings.face_recognition_threshold = 0.45
    mock_settings.face_recognition_model = "buffalo_sc"
    mock_settings.persons_path = str(tmp_path / "persons")
    mock_settings.app_version = "1.0.138"
    mock_settings.storage_path = str(tmp_path)
    # Make async methods return coroutines
    mock_frs.initialize = AsyncMock()
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


def test_get_persons_returns_persons_with_samples(client):
    """GET /api/persons must return persons array with samples."""
    client._mock_db.get_persons.return_value = [
        {"id": 1, "name": "Alice", "thumbnail_path": "/data/persons/1_1.jpg", "created_at": "2026-01-01"}
    ]
    client._mock_db.get_person_embeddings.return_value = [
        {"id": 1, "person_id": 1, "thumbnail_path": "/data/persons/1_1.jpg", "created_at": "2026-01-01"}
    ]
    resp = client.get("/api/persons")
    assert resp.status_code == 200
    data = resp.json()
    assert "persons" in data
    p = data["persons"][0]
    assert p["name"] == "Alice"
    assert "sample_count" in p
    assert "samples" in p
    assert p["samples"][0]["thumbnail_path"] == "api/persons/1/samples/1/thumbnail"


def test_patch_person_renames(client):
    """PATCH /api/persons/{id} must update name."""
    client._mock_db.rename_person.return_value = True
    resp = client.patch("/api/persons/1", json={"name": "Alicia"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Alicia"


def test_patch_person_empty_name_returns_422(client):
    """PATCH /api/persons/{id} with empty name must return 422."""
    resp = client.patch("/api/persons/1", json={"name": "   "})
    assert resp.status_code == 422


def test_patch_person_not_found_returns_404(client):
    """PATCH /api/persons/{id} when person missing must return 404."""
    client._mock_db.rename_person.return_value = False
    resp = client.patch("/api/persons/99", json={"name": "Alice"})
    assert resp.status_code == 404


def test_delete_person_returns_204(client):
    """DELETE /api/persons/{id} must return 204."""
    client._mock_frs.delete_person.return_value = True
    resp = client.delete("/api/persons/1")
    assert resp.status_code == 204


def test_delete_person_not_found_returns_404(client):
    client._mock_frs.delete_person.return_value = False
    resp = client.delete("/api/persons/99")
    assert resp.status_code == 404


def test_get_person_thumbnail_from_db(client, tmp_path):
    """GET /api/persons/{id}/thumbnail reads thumbnail_path from DB."""
    thumb = tmp_path / "persons" / "1_1.jpg"
    thumb.parent.mkdir(parents=True, exist_ok=True)
    thumb.write_bytes(b"JFIF")
    client._mock_db.get_person.return_value = {
        "id": 1, "name": "Alice", "thumbnail_path": str(thumb)
    }
    resp = client.get("/api/persons/1/thumbnail")
    assert resp.status_code == 200


def test_get_person_thumbnail_null_returns_404(client):
    """GET /api/persons/{id}/thumbnail returns 404 when no thumbnail set."""
    client._mock_db.get_person.return_value = {"id": 1, "name": "Alice", "thumbnail_path": None}
    resp = client.get("/api/persons/1/thumbnail")
    assert resp.status_code == 404
