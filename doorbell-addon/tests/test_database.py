"""Tests for database.py — new tables, migration, and CRUD methods."""
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
