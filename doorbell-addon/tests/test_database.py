"""Tests for database.py — new tables, migration, and CRUD methods."""
import io
import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock


def make_db(tmp_path):
    """Create a fresh DatabaseManager with a temp database."""
    import src.config as config_mod
    import src.database as db_mod
    # database_path = storage_path + "/database/doorbell.db"
    db_dir = str(tmp_path / "database")
    os.makedirs(db_dir, exist_ok=True)
    with patch.object(config_mod.settings, 'storage_path', str(tmp_path)):
        with patch.object(db_mod, 'settings', config_mod.settings):
            manager = db_mod.DatabaseManager()
    return manager


def test_fresh_db_creates_person_embeddings_table(tmp_path):
    """person_embeddings table must exist after init."""
    mgr = make_db(tmp_path)
    with sqlite3.connect(mgr.db_path) as conn:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
    assert "person_embeddings" in tables


def test_fresh_db_creates_face_crops_table(tmp_path):
    """face_crops table must exist after init."""
    mgr = make_db(tmp_path)
    with sqlite3.connect(mgr.db_path) as conn:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
    assert "face_crops" in tables


def test_fresh_db_known_persons_has_no_embedding_column(tmp_path):
    """Fresh known_persons table must NOT have an embedding column."""
    mgr = make_db(tmp_path)
    with sqlite3.connect(mgr.db_path) as conn:
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(known_persons)"
        ).fetchall()]
    assert "embedding" not in cols


def test_migration_copies_embedding_to_person_embeddings(tmp_path):
    """Migration must move existing embeddings to person_embeddings."""
    import src.config as config_mod
    import src.database as db_mod
    # database_path = storage_path + "/database/doorbell.db"
    db_dir = str(tmp_path / "database")
    os.makedirs(db_dir, exist_ok=True)
    db_file = str(tmp_path / "database" / "doorbell.db")

    # Create OLD schema manually
    with sqlite3.connect(db_file) as conn:
        conn.execute("""
            CREATE TABLE known_persons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                embedding BLOB NOT NULL,
                thumbnail_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE doorbell_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                image_path TEXT NOT NULL,
                ai_message TEXT, weather_condition TEXT,
                weather_temperature REAL, weather_humidity REAL,
                faces_detected INT DEFAULT 0, face_data TEXT
            )
        """)
        # Use raw bytes to simulate a serialised embedding (numpy not required)
        fake_embedding = bytes([0x01, 0x02, 0x03, 0x04])
        conn.execute(
            "INSERT INTO known_persons (name, embedding, thumbnail_path) VALUES (?, ?, ?)",
            ("Alice", fake_embedding, "/data/persons/1.jpg")
        )
        conn.commit()

    with patch.object(config_mod.settings, 'storage_path', str(tmp_path)):
        with patch.object(db_mod, 'settings', config_mod.settings):
            manager = db_mod.DatabaseManager()

    # embedding column must be gone
    with sqlite3.connect(db_file) as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(known_persons)").fetchall()]
        assert "embedding" not in cols
        # embedding must be in person_embeddings
        rows = conn.execute("SELECT person_id, embedding FROM person_embeddings").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == 1  # person_id preserved


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_embedding_bytes():
    import numpy as np
    buf = io.BytesIO()
    np.save(buf, np.array([0.1, 0.2, 0.3], dtype="float32"))
    return buf.getvalue()


# ── add_person (new signature) ─────────────────────────────────────────────

def test_add_person_returns_int(tmp_path):
    """add_person(name) must return integer person_id."""
    mgr = make_db(tmp_path)
    pid = mgr.add_person("Alice")
    assert isinstance(pid, int)
    assert pid > 0


def test_add_person_stores_no_embedding(tmp_path):
    """add_person must NOT insert into person_embeddings."""
    mgr = make_db(tmp_path)
    mgr.add_person("Alice")
    with sqlite3.connect(mgr.db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM person_embeddings").fetchone()[0]
    assert count == 0


# ── add_person_embedding ───────────────────────────────────────────────────

def test_add_person_embedding_returns_id(tmp_path):
    mgr = make_db(tmp_path)
    pid = mgr.add_person("Alice")
    emb_id = mgr.add_person_embedding(pid, _make_embedding_bytes(), None)
    assert isinstance(emb_id, int)


def test_add_person_embedding_stores_embedding(tmp_path):
    mgr = make_db(tmp_path)
    pid = mgr.add_person("Alice")
    emb_bytes = _make_embedding_bytes()
    mgr.add_person_embedding(pid, emb_bytes, "/persons/1_1.jpg")
    with sqlite3.connect(mgr.db_path) as conn:
        row = conn.execute(
            "SELECT person_id, embedding, thumbnail_path FROM person_embeddings"
        ).fetchone()
    assert row[0] == pid
    assert row[1] == emb_bytes
    assert row[2] == "/persons/1_1.jpg"


# ── update_person_embedding_thumbnail ─────────────────────────────────────

def test_update_person_embedding_thumbnail(tmp_path):
    mgr = make_db(tmp_path)
    pid = mgr.add_person("Alice")
    emb_id = mgr.add_person_embedding(pid, _make_embedding_bytes(), None)
    mgr.update_person_embedding_thumbnail(emb_id, "/persons/1_1.jpg")
    with sqlite3.connect(mgr.db_path) as conn:
        path = conn.execute(
            "SELECT thumbnail_path FROM person_embeddings WHERE id=?", (emb_id,)
        ).fetchone()[0]
    assert path == "/persons/1_1.jpg"


# ── delete_person_embedding ────────────────────────────────────────────────

def test_delete_person_embedding(tmp_path):
    mgr = make_db(tmp_path)
    pid = mgr.add_person("Alice")
    emb_id = mgr.add_person_embedding(pid, _make_embedding_bytes(), None)
    assert mgr.delete_person_embedding(emb_id) is True
    with sqlite3.connect(mgr.db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM person_embeddings").fetchone()[0]
    assert count == 0


def test_delete_person_embedding_missing_returns_false(tmp_path):
    mgr = make_db(tmp_path)
    assert mgr.delete_person_embedding(9999) is False


# ── get_person_embeddings ──────────────────────────────────────────────────

def test_get_person_embeddings_returns_list(tmp_path):
    mgr = make_db(tmp_path)
    pid = mgr.add_person("Alice")
    mgr.add_person_embedding(pid, _make_embedding_bytes(), "/p/1_1.jpg")
    mgr.add_person_embedding(pid, _make_embedding_bytes(), "/p/1_2.jpg")
    rows = mgr.get_person_embeddings(pid)
    assert len(rows) == 2
    assert rows[0]["person_id"] == pid


# ── get_all_embeddings ─────────────────────────────────────────────────────

def test_get_all_embeddings_includes_person_name(tmp_path):
    mgr = make_db(tmp_path)
    pid = mgr.add_person("Alice")
    mgr.add_person_embedding(pid, _make_embedding_bytes(), None)
    rows = mgr.get_all_embeddings()
    assert len(rows) == 1
    assert rows[0]["name"] == "Alice"
    assert rows[0]["person_id"] == pid
    assert "embedding" in rows[0]


# ── update_person_thumbnail (Optional[str]) ────────────────────────────────

def test_update_person_thumbnail_accepts_none(tmp_path):
    """update_person_thumbnail must accept None (avatar reset)."""
    mgr = make_db(tmp_path)
    pid = mgr.add_person("Alice")
    mgr.update_person_thumbnail(pid, None)  # must not raise
    with sqlite3.connect(mgr.db_path) as conn:
        val = conn.execute(
            "SELECT thumbnail_path FROM known_persons WHERE id=?", (pid,)
        ).fetchone()[0]
    assert val is None


# ── face_crops CRUD ────────────────────────────────────────────────────────

def test_add_face_crop(tmp_path):
    mgr = make_db(tmp_path)
    event = mgr.add_doorbell_event(image_path="/img/test.jpg")
    crop_id = mgr.add_face_crop(event.id, "/face_crops/42_0.jpg")
    assert isinstance(crop_id, int)


def test_get_face_crops_default_dismissed_false(tmp_path):
    mgr = make_db(tmp_path)
    event = mgr.add_doorbell_event(image_path="/img/test.jpg")
    mgr.add_face_crop(event.id, "/face_crops/42_0.jpg")
    crops = mgr.get_face_crops(dismissed=False)
    assert len(crops) == 1
    assert crops[0]["dismissed"] == 0


def test_get_face_crops_dismissed_not_returned_by_default(tmp_path):
    mgr = make_db(tmp_path)
    event = mgr.add_doorbell_event(image_path="/img/test.jpg")
    crop_id = mgr.add_face_crop(event.id, "/face_crops/42_0.jpg")
    mgr.dismiss_face_crop(crop_id)
    crops = mgr.get_face_crops(dismissed=False)
    assert len(crops) == 0


def test_get_face_crops_includes_event_timestamp(tmp_path):
    mgr = make_db(tmp_path)
    event = mgr.add_doorbell_event(image_path="/img/test.jpg")
    mgr.add_face_crop(event.id, "/face_crops/42_0.jpg")
    crops = mgr.get_face_crops()
    assert "event_timestamp" in crops[0]


def test_get_face_crop_count(tmp_path):
    mgr = make_db(tmp_path)
    event = mgr.add_doorbell_event(image_path="/img/test.jpg")
    mgr.add_face_crop(event.id, "/face_crops/42_0.jpg")
    mgr.add_face_crop(event.id, "/face_crops/42_1.jpg")
    assert mgr.get_face_crop_count(dismissed=False) == 2


def test_dismiss_face_crop(tmp_path):
    mgr = make_db(tmp_path)
    event = mgr.add_doorbell_event(image_path="/img/test.jpg")
    crop_id = mgr.add_face_crop(event.id, "/face_crops/42_0.jpg")
    mgr.dismiss_face_crop(crop_id)
    crops = mgr.get_face_crops(dismissed=True)
    assert len(crops) == 1
    assert crops[0]["dismissed"] == 1
