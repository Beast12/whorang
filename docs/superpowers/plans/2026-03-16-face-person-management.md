# Face / Person Management Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend WhoRang's face recognition to support multiple photo samples per person, an unrecognised-faces inbox for naming new faces, and full CRUD for persons and their samples.

**Architecture:** New `person_embeddings` and `face_crops` SQLite tables replace the single-embedding `known_persons.embedding` column. The recognition cache changes from `{person_id: embedding}` to `{embedding_id: (person_id, name, embedding)}`. Unrecognised face crops are saved on every ring event and reviewed via a two-tab Persons page. All new JS lives in `persons.js` (loaded globally for the nav badge).

**Tech Stack:** FastAPI, SQLite, Pydantic v2, Jinja2, Bootstrap 5, InsightFace (via existing `face_recognition_service.py`), NumPy, Pillow

**Spec:** `docs/superpowers/specs/2026-03-16-face-person-management-design.md`

---

## Before You Start

All commands run from the repo root (`/home/koen/Github/whorang/`).

**Linting (run after every chunk):**
```bash
flake8 doorbell-addon/src/ --count --select=E9,F63,F7,F82 --show-source --statistics
mypy doorbell-addon/src/ --config-file doorbell-addon/mypy.ini
```

**Tests (run after every task that adds tests):**
```bash
cd doorbell-addon && python -m pytest tests/ -v
```

> Tests require: `pip install pytest pytest-asyncio httpx fastapi pydantic pydantic-settings structlog pillow`
> Set `STORAGE_PATH=/tmp/test_whorang` before running.

**Docker build (run before every commit that changes behaviour):**
```bash
cd doorbell-addon && docker build --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:bookworm -t whorang-test .
```

---

## Chunk 1: Foundation — Database, Config, Utils

### Task 1: `face_crops_path` property + `ensure_directories` update

**Files:**
- Modify: `doorbell-addon/src/config.py`
- Modify: `doorbell-addon/src/utils.py`
- Create: `doorbell-addon/tests/conftest.py`
- Create: `doorbell-addon/tests/test_config_utils.py`

- [ ] **Step 1: Create test infrastructure**

Create `doorbell-addon/tests/conftest.py`:
```python
"""Shared pytest fixtures for WhoRang tests."""
import os
import sys
import pytest
from unittest.mock import MagicMock

# Make src importable without package prefix
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
```

- [ ] **Step 2: Write failing tests for config and utils**

Create `doorbell-addon/tests/test_config_utils.py`:
```python
"""Tests for config.py and utils.py additions."""
import os
import pytest
from unittest.mock import patch, MagicMock


def test_face_crops_path_property(tmp_path):
    """face_crops_path should be {storage_path}/face_crops."""
    import importlib
    import src.config as config_mod
    with patch.object(config_mod.settings, 'storage_path', str(tmp_path)):
        assert config_mod.settings.face_crops_path == str(tmp_path / "face_crops")


def test_ensure_directories_creates_face_crops_path(tmp_path):
    """ensure_directories must create the face_crops directory."""
    import src.utils as utils_mod
    import src.config as config_mod
    with patch.object(config_mod.settings, 'storage_path', str(tmp_path)), \
         patch.object(config_mod.settings, 'images_path', str(tmp_path / "images")), \
         patch.object(config_mod.settings, 'persons_path', str(tmp_path / "persons")):
        with patch('src.utils.settings', config_mod.settings):
            utils_mod.ensure_directories()
    assert (tmp_path / "face_crops").is_dir()
```

- [ ] **Step 3: Run tests — expect FAIL**

```bash
cd doorbell-addon && python -m pytest tests/test_config_utils.py -v
```
Expected: `FAILED` — `AttributeError: Settings object has no attribute 'face_crops_path'`

- [ ] **Step 4: Implement — add `face_crops_path` to `config.py`**

In `doorbell-addon/src/config.py`, after the `insightface_models_path` property (line 64), add:
```python
    @property
    def face_crops_path(self) -> str:
        """Get the face crops directory path."""
        return os.path.join(self.storage_path, "face_crops")
```

- [ ] **Step 5: Implement — add `face_crops_path` to `utils.py` `ensure_directories`**

In `doorbell-addon/src/utils.py`, change `ensure_directories` (line 166–175):
```python
def ensure_directories():
    """Ensure all required directories exist."""
    for directory in [
        settings.storage_path,
        settings.images_path,
        os.path.dirname(settings.database_path),
        settings.persons_path,
        settings.face_crops_path,
    ]:
        os.makedirs(directory, exist_ok=True)
        logger.info("Directory ensured", path=directory)
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
cd doorbell-addon && python -m pytest tests/test_config_utils.py -v
```

- [ ] **Step 7: Lint + type check**

```bash
flake8 doorbell-addon/src/ --count --select=E9,F63,F7,F82 --show-source --statistics
mypy doorbell-addon/src/ --config-file doorbell-addon/mypy.ini
```

- [ ] **Step 8: Commit**

```bash
git add doorbell-addon/src/config.py doorbell-addon/src/utils.py \
        doorbell-addon/tests/conftest.py doorbell-addon/tests/test_config_utils.py
git commit -m "feat: add face_crops_path to config and ensure_directories"
```

---

### Task 2: New database tables + migration

**Files:**
- Modify: `doorbell-addon/src/database.py`
- Create: `doorbell-addon/tests/test_database.py`

- [ ] **Step 1: Write failing tests for new tables + migration**

Create `doorbell-addon/tests/test_database.py`:
```python
"""Tests for database.py — new tables, migration, and CRUD methods."""
import os
import io
import sqlite3
import pytest
from unittest.mock import patch, MagicMock


def make_db(tmp_path):
    """Create a fresh DatabaseManager with a temp database."""
    import src.database as db_mod
    mock_settings = MagicMock()
    mock_settings.database_path = str(tmp_path / "db" / "test.db")
    mock_settings.storage_path = str(tmp_path)
    os.makedirs(str(tmp_path / "db"), exist_ok=True)
    with patch.object(db_mod, 'settings', mock_settings):
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
    import src.database as db_mod
    mock_settings = MagicMock()
    db_file = str(tmp_path / "db" / "old.db")
    mock_settings.database_path = db_file
    os.makedirs(str(tmp_path / "db"), exist_ok=True)

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
        import numpy as np
        buf = io.BytesIO()
        np.save(buf, np.array([0.1, 0.2, 0.3]))
        conn.execute(
            "INSERT INTO known_persons (name, embedding, thumbnail_path) VALUES (?, ?, ?)",
            ("Alice", buf.getvalue(), "/data/persons/1.jpg")
        )
        conn.commit()

    with patch.object(db_mod, 'settings', mock_settings):
        manager = db_mod.DatabaseManager()

    # embedding column must be gone
    with sqlite3.connect(db_file) as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(known_persons)").fetchall()]
        assert "embedding" not in cols
        # embedding must be in person_embeddings
        rows = conn.execute("SELECT person_id, embedding FROM person_embeddings").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == 1  # person_id preserved
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd doorbell-addon && python -m pytest tests/test_database.py -v
```
Expected: `FAILED` — tables don't exist yet, embedding column still present

- [ ] **Step 3: Implement new `_init_database` in `database.py`**

Replace the entire `_init_database` method (lines 46–101) in `doorbell-addon/src/database.py`:

```python
    def _init_database(self):
        """Initialize the database with required tables."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            # ── Core events table ───────────────────────────────────────────
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS doorbell_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    image_path TEXT NOT NULL,
                    ai_message TEXT,
                    weather_condition TEXT,
                    weather_temperature REAL,
                    weather_humidity REAL,
                    faces_detected INT DEFAULT 0,
                    face_data TEXT
                )
                """
            )
            for col, col_type in [
                ("ai_message", "TEXT"),
                ("weather_condition", "TEXT"),
                ("weather_temperature", "REAL"),
                ("weather_humidity", "REAL"),
                ("faces_detected", "INT DEFAULT 0"),
                ("face_data", "TEXT"),
            ]:
                try:
                    conn.execute(
                        f"ALTER TABLE doorbell_events ADD COLUMN {col} {col_type}"
                    )
                    conn.commit()
                except sqlite3.OperationalError:
                    pass
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_timestamp "
                "ON doorbell_events (timestamp)"
            )

            # ── Known persons (no embedding column) ────────────────────────
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS known_persons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    thumbnail_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # ── Per-person face embeddings ──────────────────────────────────
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS person_embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_id INTEGER NOT NULL
                        REFERENCES known_persons(id) ON DELETE CASCADE,
                    embedding BLOB NOT NULL,
                    thumbnail_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # ── Unrecognised face crops inbox ───────────────────────────────
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS face_crops (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL
                        REFERENCES doorbell_events(id) ON DELETE CASCADE,
                    image_path TEXT NOT NULL,
                    dismissed BOOLEAN NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_face_crops_dismissed "
                "ON face_crops (dismissed)"
            )
            conn.commit()

            # ── Migration: move embedding column out of known_persons ───────
            # Must run AFTER all three tables above exist (same connection).
            existing_cols = [
                r[1] for r in conn.execute(
                    "PRAGMA table_info(known_persons)"
                ).fetchall()
            ]
            if "embedding" in existing_cols:
                self._migrate_remove_embedding_column(conn)

    def _migrate_remove_embedding_column(self, conn: sqlite3.Connection) -> None:
        """Move embeddings from known_persons into person_embeddings, then drop the column."""
        logger.info("Migrating: moving embeddings from known_persons to person_embeddings")
        conn.execute(
            """
            INSERT INTO person_embeddings (person_id, embedding, thumbnail_path, created_at)
            SELECT id, embedding, thumbnail_path, created_at
            FROM known_persons
            WHERE embedding IS NOT NULL
            """
        )
        conn.execute(
            """
            CREATE TABLE known_persons_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                thumbnail_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT INTO known_persons_new (id, name, thumbnail_path, created_at) "
            "SELECT id, name, thumbnail_path, created_at FROM known_persons"
        )
        conn.execute("DROP TABLE known_persons")
        conn.execute("ALTER TABLE known_persons_new RENAME TO known_persons")
        conn.commit()
        logger.info("Migration complete: embedding column removed from known_persons")
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd doorbell-addon && python -m pytest tests/test_database.py::test_fresh_db_creates_person_embeddings_table \
  tests/test_database.py::test_fresh_db_creates_face_crops_table \
  tests/test_database.py::test_fresh_db_known_persons_has_no_embedding_column \
  tests/test_database.py::test_migration_copies_embedding_to_person_embeddings -v
```

- [ ] **Step 5: Lint + type check**

```bash
flake8 doorbell-addon/src/ --count --select=E9,F63,F7,F82 --show-source --statistics
mypy doorbell-addon/src/ --config-file doorbell-addon/mypy.ini
```

- [ ] **Step 6: Commit**

```bash
git add doorbell-addon/src/database.py doorbell-addon/tests/test_database.py
git commit -m "feat: add person_embeddings and face_crops tables with migration"
```

---

### Task 3: New database CRUD methods

**Files:**
- Modify: `doorbell-addon/src/database.py`
- Modify: `doorbell-addon/tests/test_database.py`

- [ ] **Step 1: Write failing tests for new CRUD methods**

Append to `doorbell-addon/tests/test_database.py`:
```python

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
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd doorbell-addon && python -m pytest tests/test_database.py -v -k "not migration and not fresh_db"
```
Expected: multiple `AttributeError` / `TypeError` failures — methods don't exist yet.

- [ ] **Step 3: Implement new CRUD methods in `database.py`**

**Replace `add_person` method** (lines 138–147) with new signature:
```python
    def add_person(self, name: str) -> int:
        """Add a known person. Returns new person id."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO known_persons (name) VALUES (?)",
                (name,),
            )
            conn.commit()
            assert cursor.lastrowid is not None
            return cursor.lastrowid
```

**Update `update_person_thumbnail` signature** (line 169) to accept `Optional[str]`:
```python
    def update_person_thumbnail(self, person_id: int, path: Optional[str]) -> None:
        """Update thumbnail path for a person (pass None to clear avatar)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE known_persons SET thumbnail_path = ? WHERE id = ?",
                (path, person_id),
            )
            conn.commit()
```

**Remove `get_person` method** (it referenced `embedding` column — replace with simpler version):
```python
    def get_person(self, person_id: int) -> Optional[dict]:
        """Get a single person by ID (no embedding)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT id, name, thumbnail_path, created_at FROM known_persons WHERE id = ?",
                (person_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
```

**Add new methods after `delete_person`** (after line 185):
```python
    # ── Person embeddings ──────────────────────────────────────────────────

    def add_person_embedding(
        self, person_id: int, embedding_bytes: bytes, thumbnail_path: Optional[str]
    ) -> int:
        """Insert a face embedding for a person. Returns new embedding id."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO person_embeddings (person_id, embedding, thumbnail_path) "
                "VALUES (?, ?, ?)",
                (person_id, embedding_bytes, thumbnail_path),
            )
            conn.commit()
            assert cursor.lastrowid is not None
            return cursor.lastrowid

    def update_person_embedding_thumbnail(self, emb_id: int, thumbnail_path: str) -> None:
        """Set the thumbnail path for a person_embeddings row."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE person_embeddings SET thumbnail_path = ? WHERE id = ?",
                (thumbnail_path, emb_id),
            )
            conn.commit()

    def delete_person_embedding(self, emb_id: int) -> bool:
        """Delete one embedding. Returns True if deleted."""
        with sqlite3.connect(self.db_path) as conn:
            deleted = conn.execute(
                "DELETE FROM person_embeddings WHERE id = ?", (emb_id,)
            ).rowcount
            conn.commit()
        return deleted > 0

    def get_person_embeddings(self, person_id: int) -> List[dict]:
        """Get all embeddings for a person, ordered by id ASC."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT id, person_id, thumbnail_path, created_at "
                "FROM person_embeddings WHERE person_id = ? ORDER BY id ASC",
                (person_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_embeddings(self) -> List[dict]:
        """Get all embeddings with their person name (for cache rebuild)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT pe.id, pe.person_id, kp.name, pe.embedding "
                "FROM person_embeddings pe "
                "JOIN known_persons kp ON pe.person_id = kp.id"
            )
            return [dict(row) for row in cursor.fetchall()]

    # ── Face crops inbox ───────────────────────────────────────────────────

    def add_face_crop(self, event_id: int, image_path: str) -> int:
        """Insert an unrecognised face crop. Returns new crop id."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO face_crops (event_id, image_path) VALUES (?, ?)",
                (event_id, image_path),
            )
            conn.commit()
            assert cursor.lastrowid is not None
            return cursor.lastrowid

    def dismiss_face_crop(self, crop_id: int) -> None:
        """Mark a face crop as dismissed."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE face_crops SET dismissed = 1 WHERE id = ?", (crop_id,)
            )
            conn.commit()

    def get_face_crops(self, dismissed: bool = False) -> List[dict]:
        """Get face crops with event timestamp (JOIN doorbell_events)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT fc.id, fc.event_id, fc.image_path, fc.dismissed, "
                "fc.created_at, de.timestamp as event_timestamp "
                "FROM face_crops fc "
                "JOIN doorbell_events de ON fc.event_id = de.id "
                "WHERE fc.dismissed = ? "
                "ORDER BY fc.created_at DESC",
                (1 if dismissed else 0,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_face_crop(self, crop_id: int) -> Optional[dict]:
        """Get a single face crop by id."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT fc.id, fc.event_id, fc.image_path, fc.dismissed, "
                "fc.created_at, de.timestamp as event_timestamp "
                "FROM face_crops fc "
                "JOIN doorbell_events de ON fc.event_id = de.id "
                "WHERE fc.id = ?",
                (crop_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_face_crop_count(self, dismissed: bool = False) -> int:
        """Return count of face crops matching dismissed flag."""
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM face_crops WHERE dismissed = ?",
                (1 if dismissed else 0,),
            ).fetchone()[0]
```

- [ ] **Step 4: Run all database tests — expect PASS**

```bash
cd doorbell-addon && python -m pytest tests/test_database.py -v
```

- [ ] **Step 5: Lint + type check**

```bash
flake8 doorbell-addon/src/ --count --select=E9,F63,F7,F82 --show-source --statistics
mypy doorbell-addon/src/ --config-file doorbell-addon/mypy.ini
```

- [ ] **Step 6: Commit**

```bash
git add doorbell-addon/src/database.py doorbell-addon/tests/test_database.py
git commit -m "feat: add person_embeddings and face_crops CRUD methods to database"
```

---

## Chunk 2: Recognition Service

### Task 4: `IdentifiedFace.person_id` + cache change + `_refresh_embeddings_cache_sync`

**Files:**
- Modify: `doorbell-addon/src/face_recognition_service.py`
- Create: `doorbell-addon/tests/test_face_recognition_service.py`

- [ ] **Step 1: Write failing tests**

Create `doorbell-addon/tests/test_face_recognition_service.py`:
```python
"""Tests for face_recognition_service.py."""
import io
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def make_embedding_bytes(values):
    import numpy as np
    buf = io.BytesIO()
    np.save(buf, np.array(values, dtype="float32"))
    return buf.getvalue()


def test_identified_face_has_person_id_field():
    """IdentifiedFace must have a person_id field."""
    from face_recognition_service import IdentifiedFace
    face = IdentifiedFace(bbox=(0, 0, 10, 10), name="Alice", score=0.9, det_score=0.99)
    assert hasattr(face, 'person_id')
    assert face.person_id is None  # default


def test_refresh_cache_builds_new_format(tmp_path):
    """_refresh_embeddings_cache_sync must build {emb_id: (pid, name, emb)} cache."""
    import numpy as np
    from face_recognition_service import FaceRecognitionService

    emb_bytes = make_embedding_bytes([0.1, 0.2, 0.3])
    mock_db = MagicMock()
    mock_db.get_all_embeddings.return_value = [
        {"id": 5, "person_id": 1, "name": "Alice", "embedding": emb_bytes}
    ]

    svc = FaceRecognitionService.__new__(FaceRecognitionService)
    svc._embeddings_cache = {}
    svc._ready = False
    svc._model = None

    with patch('face_recognition_service.db', mock_db):
        svc._refresh_embeddings_cache_sync()

    assert 5 in svc._embeddings_cache
    person_id, person_name, emb = svc._embeddings_cache[5]
    assert person_id == 1
    assert person_name == "Alice"
    assert isinstance(emb, np.ndarray)
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd doorbell-addon && python -m pytest tests/test_face_recognition_service.py -v
```

- [ ] **Step 3: Implement changes in `face_recognition_service.py`**

**Update `IdentifiedFace` dataclass** (line 24–31) to add `person_id`:
```python
@dataclass
class IdentifiedFace:
    """Face matched against known persons."""

    bbox: tuple
    name: str        # person name or "Unknown"
    score: float     # cosine similarity (0.0 for Unknown)
    det_score: float
    person_id: Optional[int] = None  # None for Unknown
```

**Update `_embeddings_cache` type** in `__init__` (line 40):
```python
    def __init__(self):
        self._model = None
        self._ready = False
        self._embeddings_cache: Dict[int, Any] = {}  # {embedding_id: (person_id, name, emb)}
```

**Replace `_refresh_embeddings_cache_sync`** (lines 184–198):
```python
    def _refresh_embeddings_cache_sync(self) -> None:
        import io
        import numpy as np
        from .database import db
        cache: Dict[int, Any] = {}
        for row in db.get_all_embeddings():
            try:
                buf = io.BytesIO(row["embedding"])
                emb = np.load(buf, allow_pickle=False)
                cache[row["id"]] = (row["person_id"], row["name"], emb)
            except Exception as e:
                logger.warning(
                    "Failed to load embedding",
                    embedding_id=row["id"],
                    error=str(e),
                )
        self._embeddings_cache = cache
        logger.info("Embeddings cache refreshed", count=len(cache))
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd doorbell-addon && python -m pytest tests/test_face_recognition_service.py -v
```

- [ ] **Step 5: Lint + type check**

```bash
flake8 doorbell-addon/src/ --count --select=E9,F63,F7,F82 --show-source --statistics
mypy doorbell-addon/src/ --config-file doorbell-addon/mypy.ini
```

- [ ] **Step 6: Commit**

```bash
git add doorbell-addon/src/face_recognition_service.py \
        doorbell-addon/tests/test_face_recognition_service.py
git commit -m "feat: add IdentifiedFace.person_id and multi-embedding cache"
```

---

### Task 5: Revised `identify_faces` logic

**Files:**
- Modify: `doorbell-addon/src/face_recognition_service.py`
- Modify: `doorbell-addon/tests/test_face_recognition_service.py`

- [ ] **Step 1: Write failing tests for multi-embedding identify_faces**

Append to `doorbell-addon/tests/test_face_recognition_service.py`:
```python

def make_service_with_cache(embeddings):
    """Build a FaceRecognitionService with a pre-populated cache."""
    import numpy as np
    from face_recognition_service import FaceRecognitionService
    svc = FaceRecognitionService.__new__(FaceRecognitionService)
    svc._model = None
    svc._ready = True
    svc._embeddings_cache = {}
    for emb_id, person_id, name, vec in embeddings:
        svc._embeddings_cache[emb_id] = (person_id, name, np.array(vec, dtype="float32"))
    return svc


def test_identify_faces_matches_known_person(tmp_path):
    """identify_faces returns person name when cosine similarity exceeds threshold."""
    import numpy as np
    from face_recognition_service import FaceResult
    # Alice's embedding is [1, 0, 0]
    svc = make_service_with_cache([(1, 10, "Alice", [1.0, 0.0, 0.0])])
    mock_settings = MagicMock()
    mock_settings.face_recognition_threshold = 0.45
    face = FaceResult(bbox=(0, 0, 50, 50), embedding=np.array([1.0, 0.0, 0.0]), det_score=0.99)
    with patch('face_recognition_service.settings', mock_settings):
        results = svc.identify_faces([face])
    assert results[0].name == "Alice"
    assert results[0].person_id == 10


def test_identify_faces_unknown_below_threshold(tmp_path):
    import numpy as np
    from face_recognition_service import FaceResult
    svc = make_service_with_cache([(1, 10, "Alice", [1.0, 0.0, 0.0])])
    mock_settings = MagicMock()
    mock_settings.face_recognition_threshold = 0.45
    # Orthogonal vector — similarity = 0
    face = FaceResult(bbox=(0, 0, 50, 50), embedding=np.array([0.0, 1.0, 0.0]), det_score=0.99)
    with patch('face_recognition_service.settings', mock_settings):
        results = svc.identify_faces([face])
    assert results[0].name == "Unknown"
    assert results[0].person_id is None


def test_identify_faces_picks_best_across_multiple_embeddings(tmp_path):
    """Multiple embeddings for the same person: pick best score."""
    import numpy as np
    from face_recognition_service import FaceResult
    # Alice has two embeddings; Bob has one
    svc = make_service_with_cache([
        (1, 10, "Alice", [0.9, 0.1, 0.0]),
        (2, 10, "Alice", [1.0, 0.0, 0.0]),  # better match for [1,0,0]
        (3, 20, "Bob",   [0.0, 1.0, 0.0]),
    ])
    mock_settings = MagicMock()
    mock_settings.face_recognition_threshold = 0.45
    face = FaceResult(bbox=(0, 0, 50, 50), embedding=np.array([1.0, 0.0, 0.0]), det_score=0.99)
    with patch('face_recognition_service.settings', mock_settings):
        results = svc.identify_faces([face])
    assert results[0].name == "Alice"
    assert results[0].person_id == 10


def test_identify_faces_picks_best_person_not_best_embedding(tmp_path):
    """When two persons both exceed threshold, pick the one with higher score."""
    import numpy as np
    from face_recognition_service import FaceResult
    svc = make_service_with_cache([
        (1, 10, "Alice", [0.95, 0.05, 0.0]),
        (2, 20, "Bob",   [0.80, 0.20, 0.0]),
    ])
    mock_settings = MagicMock()
    mock_settings.face_recognition_threshold = 0.45
    face = FaceResult(bbox=(0, 0, 50, 50), embedding=np.array([1.0, 0.0, 0.0]), det_score=0.99)
    with patch('face_recognition_service.settings', mock_settings):
        results = svc.identify_faces([face])
    assert results[0].name == "Alice"
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd doorbell-addon && python -m pytest tests/test_face_recognition_service.py -v -k "identify"
```

- [ ] **Step 3: Implement revised `identify_faces` in `face_recognition_service.py`**

Replace the `identify_faces` method (lines 91–113):
```python
    def identify_faces(self, faces: List[FaceResult]) -> List[IdentifiedFace]:
        """Match detected faces against known persons using cosine similarity.
        Multiple embeddings per person: pick the best-scoring person.
        """
        import numpy as np
        identified = []
        for face in faces:
            emb = face.embedding
            norm_emb = emb / (np.linalg.norm(emb) + 1e-10)
            # best_per_person: {person_id: (name, best_score)}
            best_per_person: Dict[int, Any] = {}
            for _emb_id, (person_id, person_name, known_emb) in self._embeddings_cache.items():
                norm_known = known_emb / (np.linalg.norm(known_emb) + 1e-10)
                score = float(np.dot(norm_emb, norm_known))
                if score >= settings.face_recognition_threshold:
                    prev = best_per_person.get(person_id)
                    if prev is None or score > prev[1]:
                        best_per_person[person_id] = (person_name, score)
            if best_per_person:
                best_person_id = max(
                    best_per_person, key=lambda pid: best_per_person[pid][1]
                )
                best_name, best_score = best_per_person[best_person_id]
            else:
                best_person_id, best_name, best_score = None, "Unknown", 0.0
            identified.append(IdentifiedFace(
                bbox=face.bbox,
                name=best_name,
                person_id=best_person_id,
                score=round(best_score, 3),
                det_score=round(face.det_score, 3),
            ))
        return identified
```

Also remove the no-longer-needed `_get_person_name` method (lines 115–118) and update `Dict` import at the top of the file — add `Any` to `from typing import Any, Dict, List, Optional`.

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd doorbell-addon && python -m pytest tests/test_face_recognition_service.py -v
```

- [ ] **Step 5: Lint + type check**

```bash
flake8 doorbell-addon/src/ --count --select=E9,F63,F7,F82 --show-source --statistics
mypy doorbell-addon/src/ --config-file doorbell-addon/mypy.ini
```

- [ ] **Step 6: Commit**

```bash
git add doorbell-addon/src/face_recognition_service.py \
        doorbell-addon/tests/test_face_recognition_service.py
git commit -m "feat: revise identify_faces for multi-embedding matching"
```

---

### Task 6: `save_face_crop` helper + updated `add_person`/`delete_person`

**Files:**
- Modify: `doorbell-addon/src/face_recognition_service.py`
- Modify: `doorbell-addon/tests/test_face_recognition_service.py`

- [ ] **Step 1: Write failing tests**

Append to `doorbell-addon/tests/test_face_recognition_service.py`:
```python

def test_save_face_crop_creates_file(tmp_path):
    """save_face_crop must write a JPEG to face_crops_path."""
    import numpy as np
    from PIL import Image
    from face_recognition_service import FaceRecognitionService

    # Create a dummy image
    img = Image.new("RGB", (200, 200), color=(128, 64, 32))
    img_path = str(tmp_path / "test_img.jpg")
    img.save(img_path, "JPEG")

    svc = FaceRecognitionService.__new__(FaceRecognitionService)
    mock_settings = MagicMock()
    mock_settings.face_crops_path = str(tmp_path / "crops")

    with patch('face_recognition_service.settings', mock_settings):
        path = svc.save_face_crop(img_path, (10, 10, 80, 80), event_id=42, face_idx=0)

    assert os.path.isfile(path)
    assert "42_0.jpg" in path
    saved = Image.open(path)
    assert saved.size == (200, 200)


def test_save_face_crop_uses_event_idx_naming(tmp_path):
    """File name must be {event_id}_{face_idx}.jpg."""
    from PIL import Image
    from face_recognition_service import FaceRecognitionService
    img = Image.new("RGB", (300, 300))
    img_path = str(tmp_path / "img.jpg")
    img.save(img_path, "JPEG")
    svc = FaceRecognitionService.__new__(FaceRecognitionService)
    mock_settings = MagicMock()
    mock_settings.face_crops_path = str(tmp_path / "crops")
    with patch('face_recognition_service.settings', mock_settings):
        path = svc.save_face_crop(img_path, (0, 0, 100, 100), event_id=7, face_idx=2)
    assert path.endswith("7_2.jpg")
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd doorbell-addon && python -m pytest tests/test_face_recognition_service.py -v -k "save_face_crop"
```

- [ ] **Step 3: Implement `save_face_crop` in `face_recognition_service.py`**

Add `save_face_crop` method after `identify_faces`. Also update `add_person` to use new DB API and update `delete_person`.

**Add `save_face_crop` method:**
```python
    def save_face_crop(
        self, image_path: str, bbox: tuple, event_id: int, face_idx: int
    ) -> str:
        """Crop an unrecognised face and save to face_crops directory.
        bbox is (x, y, w, h) — same format returned by analyze_image().
        """
        from PIL import Image, ImageOps
        img = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
        x, y, w, h = bbox
        padding = int(max(w, h) * 0.2)
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(img.width, x + w + padding)
        y2 = min(img.height, y + h + padding)
        crop = img.crop((x1, y1, x2, y2)).resize((200, 200))
        os.makedirs(settings.face_crops_path, exist_ok=True)
        path = os.path.join(settings.face_crops_path, f"{event_id}_{face_idx}.jpg")
        crop.save(path, "JPEG")
        return path
```

**Replace `add_person` method** to use new DB signatures:
```python
    def add_person(self, name: str, image_path: str) -> dict:
        """Detect face in image, store embedding + thumbnail. Returns person dict."""
        import io
        import numpy as np
        from PIL import Image, ImageOps
        from .database import db

        os.makedirs(settings.persons_path, exist_ok=True)

        faces = self.analyze_image(image_path)
        if not faces:
            raise ValueError("No face detected in the uploaded image")

        best_face = max(faces, key=lambda f: f.det_score)

        # Serialize embedding
        buf = io.BytesIO()
        np.save(buf, best_face.embedding)
        embedding_bytes = buf.getvalue()

        # Create person record (no embedding in known_persons)
        person_id = db.add_person(name)

        # Crop and save thumbnail using temp-rename pattern
        thumb_path = None
        try:
            img = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
            x, y, w, h = best_face.bbox
            padding = int(max(w, h) * 0.2)
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(img.width, x + w + padding)
            y2 = min(img.height, y + h + padding)
            thumb = img.crop((x1, y1, x2, y2)).resize((200, 200))
            tmp_path = os.path.join(settings.persons_path, f"{person_id}_tmp.jpg")
            thumb.save(tmp_path, "JPEG")
            # Insert embedding, then rename file to final path
            emb_id = db.add_person_embedding(person_id, embedding_bytes, None)
            thumb_path = os.path.join(settings.persons_path, f"{person_id}_{emb_id}.jpg")
            os.rename(tmp_path, thumb_path)
            db.update_person_embedding_thumbnail(emb_id, thumb_path)
            db.update_person_thumbnail(person_id, thumb_path)
        except Exception as e:
            logger.warning("Failed to save person thumbnail", error=str(e))

        # Update cache
        self._refresh_embeddings_cache_sync()

        return {"id": person_id, "name": name, "thumbnail_path": thumb_path}
```

**Replace `delete_person` method** to collect thumbnails from `person_embeddings`:
```python
    def delete_person(self, person_id: int) -> bool:
        """Remove person from DB and cache, deleting all thumbnail files."""
        from .database import db
        # Collect all thumbnail paths before deletion
        embeddings = db.get_person_embeddings(person_id)
        thumb_paths = [e["thumbnail_path"] for e in embeddings if e["thumbnail_path"]]
        deleted = db.delete_person(person_id)
        if deleted:
            self._embeddings_cache = {
                k: v for k, v in self._embeddings_cache.items()
                if v[0] != person_id
            }
            for thumb in thumb_paths:
                try:
                    if os.path.exists(thumb):
                        os.remove(thumb)
                except Exception:
                    pass
        return deleted
```

- [ ] **Step 4: Run all service tests — expect PASS**

```bash
cd doorbell-addon && python -m pytest tests/test_face_recognition_service.py -v
```

- [ ] **Step 5: Lint + type check**

```bash
flake8 doorbell-addon/src/ --count --select=E9,F63,F7,F82 --show-source --statistics
mypy doorbell-addon/src/ --config-file doorbell-addon/mypy.ini
```

- [ ] **Step 6: Commit**

```bash
git add doorbell-addon/src/face_recognition_service.py \
        doorbell-addon/tests/test_face_recognition_service.py
git commit -m "feat: add save_face_crop helper and update add_person/delete_person"
```

---

## Chunk 3: API Endpoints + Ring Handler

### Task 7: Ring handler crop-saving step

**Files:**
- Modify: `doorbell-addon/src/app.py`

- [ ] **Step 1: Update `doorbell_ring` handler in `app.py`**

After the `db.add_doorbell_event(...)` call (around line 394–402), add the crop-saving step. The current code goes directly to `await asyncio.gather(ha_integration...)` — insert between them:

```python
        # Save unrecognised face crops after event is persisted (need event_id)
        if face_raw and settings.face_recognition_enabled and face_recognition_service.is_ready():
            identified_for_crops = face_recognition_service.identify_faces(face_raw)
            for idx, iface in enumerate(identified_for_crops):
                if iface.name == "Unknown":
                    try:
                        crop_path = await asyncio.to_thread(
                            face_recognition_service.save_face_crop,
                            image_path, iface.bbox, event.id, idx
                        )
                        db.add_face_crop(event.id, crop_path)
                    except Exception as crop_err:
                        logger.warning("Failed to save face crop", error=str(crop_err))
```

> Note: `identified` was already computed above for `face_data_json`. We call `identify_faces` a second time here to have the `IdentifiedFace` objects with `bbox`. Alternatively, save `identified` to a local variable instead of building a new list. Update the existing code:

Replace the face analysis block (lines 379–391):
```python
        faces_detected, face_data_json = 0, None
        identified: list = []
        if face_raw:
            identified = face_recognition_service.identify_faces(face_raw)
            faces_detected = len(identified)
            face_data_json = json.dumps([
                {
                    "name": f.name,
                    "bbox": list(f.bbox),
                    "score": round(f.score, 3),
                    "det_score": round(f.det_score, 3),
                }
                for f in identified
            ])
```

Then after `event = db.add_doorbell_event(...)`, add:
```python
        # Save unrecognised face crops (needs event_id, so runs after DB insert)
        for idx, iface in enumerate(identified):
            if iface.name == "Unknown":
                try:
                    crop_path = await asyncio.to_thread(
                        face_recognition_service.save_face_crop,
                        image_path, iface.bbox, event.id, idx
                    )
                    db.add_face_crop(event.id, crop_path)
                except Exception as crop_err:
                    logger.warning("Failed to save face crop", error=str(crop_err))
```

- [ ] **Step 2: Lint + type check**

```bash
flake8 doorbell-addon/src/ --count --select=E9,F63,F7,F82 --show-source --statistics
mypy doorbell-addon/src/ --config-file doorbell-addon/mypy.ini
```

- [ ] **Step 3: Commit**

```bash
git add doorbell-addon/src/app.py
git commit -m "feat: save unrecognised face crops to inbox after ring event"
```

---

### Task 8: New persons API endpoints

**Files:**
- Modify: `doorbell-addon/src/app.py`
- Create: `doorbell-addon/tests/test_api_persons.py`

- [ ] **Step 1: Write failing tests for persons API**

Create `doorbell-addon/tests/test_api_persons.py`:
```python
"""Tests for persons API endpoints."""
import os
import io
import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def client(tmp_path):
    """Create a test client with mocked dependencies."""
    from fastapi.testclient import TestClient
    import app as app_mod
    # Patch db and face_recognition_service at module level
    mock_db = MagicMock()
    mock_frs = MagicMock()
    mock_frs.is_ready.return_value = True
    mock_settings = MagicMock()
    mock_settings.face_recognition_enabled = True
    mock_settings.face_recognition_threshold = 0.45
    mock_settings.face_recognition_model = "buffalo_sc"
    mock_settings.persons_path = str(tmp_path / "persons")
    mock_settings.app_version = "1.0.138"
    mock_settings.storage_path = str(tmp_path)
    with patch.object(app_mod, 'db', mock_db), \
         patch.object(app_mod, 'face_recognition_service', mock_frs), \
         patch.object(app_mod, 'settings', mock_settings):
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
    assert p["samples"][0]["thumbnail_path"] == "/api/persons/1/samples/1/thumbnail"


def test_patch_person_renames(client):
    """PATCH /api/persons/{id} must update name."""
    client._mock_db.get_person.return_value = {"id": 1, "name": "Alice", "thumbnail_path": None}
    resp = client.patch("/api/persons/1", json={"name": "Alicia"})
    assert resp.status_code == 200
    client._mock_db.get_persons  # reset
    assert resp.json()["name"] == "Alicia"


def test_patch_person_empty_name_returns_422(client):
    """PATCH /api/persons/{id} with empty name must return 422."""
    resp = client.patch("/api/persons/1", json={"name": "   "})
    assert resp.status_code == 422


def test_patch_person_not_found_returns_404(client):
    """PATCH /api/persons/{id} when person missing must return 404."""
    client._mock_db.get_person.return_value = None
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
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd doorbell-addon && python -m pytest tests/test_api_persons.py -v
```

- [ ] **Step 3: Rewrite persons endpoints in `app.py`**

**Replace `get_persons` endpoint** (lines 721–725):
```python
@app.get("/api/persons")
async def get_persons():
    """Get all known persons with their sample embeddings."""
    persons = db.get_persons()
    result = []
    for p in persons:
        embeddings = db.get_person_embeddings(p["id"])
        thumb_url = f"/api/persons/{p['id']}/thumbnail" if p.get("thumbnail_path") else None
        samples = [
            {
                "id": e["id"],
                "thumbnail_path": f"/api/persons/{p['id']}/samples/{e['id']}/thumbnail",
                "created_at": e["created_at"],
            }
            for e in embeddings
        ]
        result.append({
            "id": p["id"],
            "name": p["name"],
            "thumbnail_path": thumb_url,
            "sample_count": len(samples),
            "samples": samples,
        })
    return {"persons": result}
```

**Replace `add_person` endpoint** (lines 728–751):
```python
@app.post("/api/persons", status_code=201)
async def add_person(name: str = Form(...), image: UploadFile = File(...)):
    """Add a known person from an uploaded image."""
    if not settings.face_recognition_enabled:
        raise HTTPException(status_code=503, detail="Face recognition is not enabled")
    name = name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name must not be empty")
    import tempfile
    suffix = os.path.splitext(image.filename or ".jpg")[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await image.read())
        tmp_path = tmp.name
    try:
        person = await asyncio.to_thread(
            face_recognition_service.add_person, name, tmp_path
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Error adding person", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
    # Return full person shape
    embeddings = db.get_person_embeddings(person["id"])
    samples = [
        {
            "id": e["id"],
            "thumbnail_path": f"/api/persons/{person['id']}/samples/{e['id']}/thumbnail",
            "created_at": e["created_at"],
        }
        for e in embeddings
    ]
    return {
        "id": person["id"],
        "name": person["name"],
        "thumbnail_path": f"/api/persons/{person['id']}/thumbnail" if person.get("thumbnail_path") else None,
        "sample_count": len(samples),
        "samples": samples,
    }
```

**Add `PATCH /api/persons/{id}` endpoint** after `add_person`:
```python
@app.patch("/api/persons/{person_id}")
async def rename_person(person_id: int, request: Request):
    """Rename a known person."""
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name must not be empty")
    person = db.get_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    with sqlite3.connect(db.db_path) as conn:
        conn.execute("UPDATE known_persons SET name = ? WHERE id = ?", (name, person_id))
        conn.commit()
    face_recognition_service.refresh_embeddings_cache()
    return {"id": person_id, "name": name}
```

> Note: import `sqlite3` at the top of `app.py` if not already present.

**Replace `delete_person` endpoint** (lines 754–760):
```python
@app.delete("/api/persons/{person_id}", status_code=204)
async def delete_person(person_id: int):
    """Delete a known person and all their sample thumbnails."""
    deleted = await asyncio.to_thread(face_recognition_service.delete_person, person_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Person not found")
```

**Replace `get_person_thumbnail` endpoint** (lines 763–769):
```python
@app.get("/api/persons/{person_id}/thumbnail")
async def get_person_thumbnail(person_id: int):
    """Serve person avatar thumbnail — reads path from DB."""
    person = db.get_person(person_id)
    if not person or not person.get("thumbnail_path"):
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    if not os.path.isfile(person["thumbnail_path"]):
        raise HTTPException(status_code=404, detail="Thumbnail file missing")
    return FileResponse(person["thumbnail_path"])
```

**Add samples endpoints** after `get_person_thumbnail`:
```python
@app.get("/api/persons/{person_id}/samples/{emb_id}/thumbnail")
async def get_sample_thumbnail(person_id: int, emb_id: int):
    """Serve a specific sample thumbnail."""
    rows = db.get_person_embeddings(person_id)
    emb = next((e for e in rows if e["id"] == emb_id), None)
    if not emb or not emb.get("thumbnail_path"):
        raise HTTPException(status_code=404, detail="Sample thumbnail not found")
    if not os.path.isfile(emb["thumbnail_path"]):
        raise HTTPException(status_code=404, detail="Thumbnail file missing")
    return FileResponse(emb["thumbnail_path"])


@app.post("/api/persons/{person_id}/samples", status_code=201)
async def add_person_sample(person_id: int, image: UploadFile = File(...)):
    """Add another face sample to an existing person."""
    if not settings.face_recognition_enabled:
        raise HTTPException(status_code=503, detail="Face recognition is not enabled")
    person = db.get_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    import tempfile, io as _io
    import numpy as np
    from PIL import Image, ImageOps
    suffix = os.path.splitext(image.filename or ".jpg")[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await image.read())
        tmp_path = tmp.name
    try:
        faces = await asyncio.to_thread(face_recognition_service.analyze_image, tmp_path)
        if not faces:
            raise HTTPException(status_code=422, detail="No face detected in uploaded image")
        best_face = max(faces, key=lambda f: f.det_score)
        buf = _io.BytesIO()
        np.save(buf, best_face.embedding)
        emb_bytes = buf.getvalue()
        # Crop thumbnail
        os.makedirs(settings.persons_path, exist_ok=True)
        img_pil = ImageOps.exif_transpose(Image.open(tmp_path)).convert("RGB")
        x, y, w, h = best_face.bbox
        padding = int(max(w, h) * 0.2)
        crop = img_pil.crop((
            max(0, x - padding), max(0, y - padding),
            min(img_pil.width, x + w + padding), min(img_pil.height, y + h + padding)
        )).resize((200, 200))
        tmp_thumb = os.path.join(settings.persons_path, f"{person_id}_tmp.jpg")
        crop.save(tmp_thumb, "JPEG")
        emb_id = db.add_person_embedding(person_id, emb_bytes, None)
        final_thumb = os.path.join(settings.persons_path, f"{person_id}_{emb_id}.jpg")
        os.rename(tmp_thumb, final_thumb)
        db.update_person_embedding_thumbnail(emb_id, final_thumb)
        # Set avatar if currently NULL
        if not person.get("thumbnail_path"):
            db.update_person_thumbnail(person_id, final_thumb)
        face_recognition_service.refresh_embeddings_cache()
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
    return {
        "id": emb_id,
        "person_id": person_id,
        "thumbnail_path": f"/api/persons/{person_id}/samples/{emb_id}/thumbnail",
        "created_at": None,
    }


@app.delete("/api/persons/{person_id}/samples/{emb_id}", status_code=204)
async def delete_person_sample(person_id: int, emb_id: int):
    """Remove a face sample from a person."""
    rows = db.get_person_embeddings(person_id)
    emb = next((e for e in rows if e["id"] == emb_id), None)
    if not emb:
        raise HTTPException(status_code=404, detail="Sample not found")
    # Delete thumbnail file
    if emb.get("thumbnail_path"):
        try:
            os.remove(emb["thumbnail_path"])
        except Exception:
            pass
    db.delete_person_embedding(emb_id)
    # Update avatar if this was the avatar
    person = db.get_person(person_id)
    if person and person.get("thumbnail_path") == emb.get("thumbnail_path"):
        remaining = db.get_person_embeddings(person_id)
        new_thumb = remaining[0]["thumbnail_path"] if remaining else None
        db.update_person_thumbnail(person_id, new_thumb)
    face_recognition_service.refresh_embeddings_cache()
```

- [ ] **Step 4: Add `import sqlite3` to `app.py` if missing**

Check line 1–20 of `app.py` for `import sqlite3`. If absent, add it after `import os`.

- [ ] **Step 5: Run tests — expect PASS**

```bash
cd doorbell-addon && python -m pytest tests/test_api_persons.py -v
```

- [ ] **Step 6: Lint + type check**

```bash
flake8 doorbell-addon/src/ --count --select=E9,F63,F7,F82 --show-source --statistics
mypy doorbell-addon/src/ --config-file doorbell-addon/mypy.ini
```

- [ ] **Step 7: Commit**

```bash
git add doorbell-addon/src/app.py doorbell-addon/tests/test_api_persons.py
git commit -m "feat: rewrite persons API endpoints with multi-sample support"
```

---

### Task 9: Face crops API endpoints

**Files:**
- Modify: `doorbell-addon/src/app.py`
- Create: `doorbell-addon/tests/test_api_face_crops.py`

- [ ] **Step 1: Write failing tests**

Create `doorbell-addon/tests/test_api_face_crops.py`:
```python
"""Tests for face crops API endpoints."""
import os, sys, io, pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient
    import app as app_mod
    mock_db = MagicMock()
    mock_frs = MagicMock()
    mock_settings = MagicMock()
    mock_settings.face_recognition_enabled = True
    mock_settings.persons_path = str(tmp_path / "persons")
    mock_settings.face_crops_path = str(tmp_path / "face_crops")
    mock_settings.app_version = "1.0.138"
    with patch.object(app_mod, 'db', mock_db), \
         patch.object(app_mod, 'face_recognition_service', mock_frs), \
         patch.object(app_mod, 'settings', mock_settings):
        with TestClient(app_mod.app) as c:
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
    client._mock_settings = MagicMock()
    import app as app_mod
    with patch.object(app_mod.settings, 'face_recognition_enabled', False):
        resp = client.get("/api/face-crops")
    # Should still return 200 (not 503), with empty list
    assert resp.status_code == 200


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
    from face_recognition_service import FaceResult
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
    face_result = FaceResult(bbox=(0,0,50,50), embedding=np.array([0.1,0.2,0.3]), det_score=0.99)
    client._mock_frs.analyze_image.return_value = [face_result]
    resp = client.post("/api/face-crops/1/assign", json={"person_id": 2})
    assert resp.status_code == 200
    assert resp.json()["person_id"] == 2


def test_assign_face_crop_both_fields_returns_422(client):
    resp = client.post("/api/face-crops/1/assign", json={"person_id": 2, "name": "Alice"})
    assert resp.status_code == 422


def test_assign_face_crop_neither_field_returns_422(client):
    resp = client.post("/api/face-crops/1/assign", json={})
    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd doorbell-addon && python -m pytest tests/test_api_face_crops.py -v
```

- [ ] **Step 3: Implement face crops endpoints in `app.py`**

Add the following endpoints after the `delete_person_sample` endpoint:

```python
# ── Face Crops Inbox ──────────────────────────────────────────────────────────


@app.get("/api/face-crops")
async def get_face_crops(dismissed: bool = False, count_only: bool = False):
    """Get unrecognised face crops inbox."""
    if not settings.face_recognition_enabled:
        return {"count": 0} if count_only else {"crops": []}
    if count_only:
        return {"count": db.get_face_crop_count(dismissed=dismissed)}
    crops = db.get_face_crops(dismissed=dismissed)
    result = []
    for c in crops:
        result.append({
            "id": c["id"],
            "event_id": c["event_id"],
            "image_path": f"/api/face-crops/{c['id']}/image",
            "dismissed": bool(c["dismissed"]),
            "created_at": c["created_at"],
            "event_timestamp": c["event_timestamp"],
        })
    return {"crops": result}


@app.get("/api/face-crops/{crop_id}/image")
async def get_face_crop_image(crop_id: int):
    """Serve a face crop image."""
    crop = db.get_face_crop(crop_id)
    if not crop:
        raise HTTPException(status_code=404, detail="Crop not found")
    if not os.path.isfile(crop["image_path"]):
        raise HTTPException(status_code=404, detail="Crop file missing")
    return FileResponse(crop["image_path"])


@app.post("/api/face-crops/{crop_id}/dismiss", status_code=204)
async def dismiss_face_crop(crop_id: int):
    """Dismiss a face crop without assigning."""
    crop = db.get_face_crop(crop_id)
    if not crop:
        raise HTTPException(status_code=404, detail="Crop not found")
    db.dismiss_face_crop(crop_id)


@app.post("/api/face-crops/{crop_id}/assign")
async def assign_face_crop(crop_id: int, request: Request):
    """Assign a face crop to an existing person or create a new one."""
    if not settings.face_recognition_enabled:
        raise HTTPException(status_code=503, detail="Face recognition is not enabled")
    data = await request.json()
    has_person_id = "person_id" in data
    has_name = "name" in data and data["name"]
    if has_person_id == has_name:  # both or neither
        raise HTTPException(
            status_code=422,
            detail="Provide exactly one of person_id or name",
        )
    crop = db.get_face_crop(crop_id)
    if not crop:
        raise HTTPException(status_code=404, detail="Crop not found")

    created_person_id = None
    if has_name:
        created_person_id = db.add_person(data["name"].strip())
        person_id = created_person_id
    else:
        person_id = int(data["person_id"])

    try:
        faces = await asyncio.to_thread(
            face_recognition_service.analyze_image, crop["image_path"]
        )
        if not faces:
            if created_person_id:
                db.delete_person(created_person_id)
            raise HTTPException(status_code=422, detail="No face detected in crop image")

        best_face = max(faces, key=lambda f: f.det_score)
        import io as _io
        import numpy as np
        buf = _io.BytesIO()
        np.save(buf, best_face.embedding)
        emb_bytes = buf.getvalue()

        os.makedirs(settings.persons_path, exist_ok=True)
        from PIL import Image, ImageOps
        img_pil = ImageOps.exif_transpose(
            Image.open(crop["image_path"])
        ).convert("RGB")
        x, y, w, h = best_face.bbox
        padding = int(max(w, h) * 0.2)
        thumb = img_pil.crop((
            max(0, x - padding), max(0, y - padding),
            min(img_pil.width, x + w + padding), min(img_pil.height, y + h + padding),
        )).resize((200, 200))
        tmp_thumb = os.path.join(settings.persons_path, f"{person_id}_tmp.jpg")
        thumb.save(tmp_thumb, "JPEG")
        emb_id = db.add_person_embedding(person_id, emb_bytes, None)
        final_thumb = os.path.join(settings.persons_path, f"{person_id}_{emb_id}.jpg")
        os.rename(tmp_thumb, final_thumb)
        db.update_person_embedding_thumbnail(emb_id, final_thumb)
        person = db.get_person(person_id)
        if person and not person.get("thumbnail_path"):
            db.update_person_thumbnail(person_id, final_thumb)
        db.dismiss_face_crop(crop_id)
        face_recognition_service.refresh_embeddings_cache()

        name = data.get("name") or (person["name"] if person else "Unknown")
        return {"person_id": person_id, "embedding_id": emb_id, "name": name}

    except HTTPException:
        raise
    except Exception as e:
        if created_person_id:
            try:
                db.delete_person(created_person_id)
            except Exception:
                pass
        logger.error("Error assigning face crop", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd doorbell-addon && python -m pytest tests/test_api_face_crops.py -v
```

- [ ] **Step 5: Run all tests**

```bash
cd doorbell-addon && python -m pytest tests/ -v
```

- [ ] **Step 6: Lint + type check**

```bash
flake8 doorbell-addon/src/ --count --select=E9,F63,F7,F82 --show-source --statistics
mypy doorbell-addon/src/ --config-file doorbell-addon/mypy.ini
```

- [ ] **Step 7: Commit**

```bash
git add doorbell-addon/src/app.py doorbell-addon/tests/test_api_face_crops.py
git commit -m "feat: add face crops inbox API endpoints"
```

---

## Chunk 4: Frontend + Version Bump

### Task 10: `base.html` nav badge + `persons.js` global script

**Files:**
- Modify: `doorbell-addon/web/templates/base.html`
- Create: `doorbell-addon/web/static/js/persons.js`

- [ ] **Step 1: Add nav badge span to `base.html`**

In `doorbell-addon/web/templates/base.html`, find the Persons nav link (line 44–47):
```html
<a class="nav-link {% if request.url.path == '/persons' %}active{% endif %}" href="persons">
    <i class="bi bi-people-fill"></i> Persons
</a>
```
Replace with:
```html
<a class="nav-link {% if request.url.path == '/persons' %}active{% endif %}" href="persons">
    <i class="bi bi-people-fill"></i> Persons
    <span id="unrecognised-count"
          style="display:none;background:#fb923c;color:#fff;border-radius:10px;
                 padding:1px 6px;font-size:10px;margin-left:4px;vertical-align:middle"></span>
</a>
```

Add `persons.js` global script tag after `face-overlay.js` (line 80):
```html
    <!-- Face Overlay JS -->
    <script src="static/js/face-overlay.js"></script>
    <!-- Persons badge polling -->
    <script src="static/js/persons.js"></script>
```

- [ ] **Step 2: Create `persons.js`**

Create `doorbell-addon/web/static/js/persons.js`:
```javascript
/**
 * persons.js — Loaded globally for nav badge polling.
 * Also contains all Persons page tab/action logic (runs only when #persons-tabs exists).
 */

// ── Nav badge polling ────────────────────────────────────────────────────────

(function () {
    var badgeEl = null;
    var frEnabled = null; // null = unchecked, true/false = result

    function updateBadge() {
        if (frEnabled === false) return;
        fetch('api/face-crops?count_only=true')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                badgeEl = badgeEl || document.getElementById('unrecognised-count');
                if (!badgeEl) return;
                var n = data.count || 0;
                if (n > 0) {
                    badgeEl.textContent = n;
                    badgeEl.style.display = 'inline-block';
                } else {
                    badgeEl.style.display = 'none';
                }
            })
            .catch(function () {});
    }

    function checkStatusThenPoll() {
        fetch('api/face-recognition/status')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                frEnabled = !!data.enabled;
                if (frEnabled) {
                    updateBadge();
                    setInterval(updateBadge, 30000);
                }
            })
            .catch(function () {});
    }

    document.addEventListener('DOMContentLoaded', checkStatusThenPoll);
})();

// ── Persons page logic ───────────────────────────────────────────────────────
// Only runs when the two-tab layout is present on /persons.

document.addEventListener('DOMContentLoaded', function () {
    if (!document.getElementById('persons-tabs')) return;

    // ── Tab switching ──────────────────────────────────────────────────────
    var tabs = document.querySelectorAll('[data-tab]');
    var panes = document.querySelectorAll('[data-pane]');

    function showTab(name) {
        tabs.forEach(function (t) {
            var active = t.dataset.tab === name;
            t.style.color = active ? 'var(--primary, #38bdf8)' : '#888';
            t.style.borderBottom = active ? '2px solid var(--primary, #38bdf8)' : '2px solid transparent';
        });
        panes.forEach(function (p) {
            p.style.display = p.dataset.pane === name ? '' : 'none';
        });
        if (name === 'unrecognised') loadCrops();
    }

    tabs.forEach(function (t) {
        t.addEventListener('click', function () { showTab(t.dataset.tab); });
    });
    showTab('known');

    // ── Inline rename ──────────────────────────────────────────────────────
    document.addEventListener('click', function (e) {
        if (!e.target.classList.contains('rename-btn')) return;
        var pid = e.target.dataset.personId;
        var nameEl = document.getElementById('person-name-' + pid);
        var input = document.createElement('input');
        input.value = nameEl.textContent.trim();
        input.style.cssText = 'font-size:13px;font-weight:600;border:1px solid #38bdf8;' +
            'background:#111;color:#e5e7eb;border-radius:4px;padding:1px 4px;width:100px';
        nameEl.replaceWith(input);
        input.focus();
        function save() {
            var newName = input.value.trim();
            if (!newName) { input.replaceWith(nameEl); return; }
            fetch('api/persons/' + pid, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: newName }),
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    nameEl.textContent = data.name;
                    input.replaceWith(nameEl);
                })
                .catch(function () { input.replaceWith(nameEl); });
        }
        input.addEventListener('blur', save);
        input.addEventListener('keydown', function (ev) {
            if (ev.key === 'Enter') save();
            if (ev.key === 'Escape') input.replaceWith(nameEl);
        });
    });

    // ── Delete person ──────────────────────────────────────────────────────
    window.deletePerson = function (personId, name) {
        if (!confirm('Remove ' + name + ' from known persons?')) return;
        fetch('api/persons/' + personId, { method: 'DELETE' })
            .then(function (r) {
                if (r.ok) {
                    var card = document.getElementById('person-card-' + personId);
                    if (card) card.closest('.col-sm-6, .col-md-4, [id^=person-card-]')
                        ? card.closest('[id^=person-card-]').parentElement.remove()
                        : card.remove();
                    location.reload();
                } else {
                    r.json().then(function (d) { alert('Error: ' + (d.detail || 'Unknown')); });
                }
            });
    };

    // ── Delete sample ──────────────────────────────────────────────────────
    window.deleteSample = function (personId, embId) {
        if (!confirm('Remove this sample?')) return;
        fetch('api/persons/' + personId + '/samples/' + embId, { method: 'DELETE' })
            .then(function (r) {
                if (r.ok) location.reload();
                else r.json().then(function (d) { alert('Error: ' + (d.detail || 'Unknown')); });
            });
    };

    // ── Add sample ─────────────────────────────────────────────────────────
    window.addSample = function (personId) {
        var input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.addEventListener('change', function () {
            if (!input.files[0]) return;
            var fd = new FormData();
            fd.append('image', input.files[0]);
            fetch('api/persons/' + personId + '/samples', { method: 'POST', body: fd })
                .then(function (r) {
                    if (r.ok) location.reload();
                    else r.json().then(function (d) {
                        alert('Error: ' + (d.detail || 'Unknown'));
                    });
                });
        });
        input.click();
    };

    // ── Add new person ─────────────────────────────────────────────────────
    window.addPerson = function () {
        var name = (document.getElementById('new-person-name') || {}).value || '';
        var photo = (document.getElementById('new-person-photo') || {}).files;
        var status = document.getElementById('add-person-status');
        name = name.trim();
        if (!name) { if (status) status.innerHTML = '<span style="color:var(--red)">Enter a name.</span>'; return; }
        if (!photo || !photo[0]) { if (status) status.innerHTML = '<span style="color:var(--red)">Select a photo.</span>'; return; }
        var fd = new FormData();
        fd.append('name', name);
        fd.append('image', photo[0]);
        fetch('api/persons', { method: 'POST', body: fd })
            .then(function (r) {
                if (r.ok) location.reload();
                else r.json().then(function (d) {
                    if (status) status.innerHTML = '<span style="color:var(--red)">Error: ' + (d.detail || 'Unknown') + '</span>';
                });
            });
    };

    // ── Unrecognised crops tab ─────────────────────────────────────────────
    var selectedCropId = null;

    function loadCrops() {
        fetch('api/face-crops?dismissed=false')
            .then(function (r) { return r.json(); })
            .then(function (data) { renderCrops(data.crops || []); })
            .catch(function () {});
    }

    function renderCrops(crops) {
        var grid = document.getElementById('crops-grid');
        var panel = document.getElementById('crop-action-panel');
        if (!grid) return;
        grid.innerHTML = '';
        if (crops.length === 0) {
            grid.innerHTML = '<p style="color:#666;font-size:13px;grid-column:1/-1">No unrecognised faces — great!</p>';
            if (panel) panel.style.display = 'none';
            return;
        }
        crops.forEach(function (crop) {
            var div = document.createElement('div');
            div.style.cssText = 'background:#1c1c1f;border-radius:8px;border:1px solid #333;overflow:hidden;cursor:pointer';
            div.id = 'crop-' + crop.id;
            var ts = (crop.event_timestamp || crop.created_at || '').slice(0, 16).replace('T', ' ');
            div.innerHTML =
                '<img src="' + crop.image_path + '" style="width:100%;height:80px;object-fit:cover" ' +
                'onerror="this.style.background=\'#333\';this.style.height=\'80px\'">' +
                '<div style="padding:4px 6px;font-size:10px;color:#888">' + ts + '</div>';
            div.addEventListener('click', function () { selectCrop(crop.id); });
            grid.appendChild(div);
        });
    }

    function selectCrop(cropId) {
        // Highlight selected
        document.querySelectorAll('[id^=crop-]').forEach(function (el) {
            el.style.border = '1px solid #333';
        });
        var el = document.getElementById('crop-' + cropId);
        if (el) el.style.border = '2px solid #38bdf8';
        selectedCropId = cropId;
        var panel = document.getElementById('crop-action-panel');
        if (panel) panel.style.display = '';
    }

    window.assignCropToPerson = function (personId) {
        if (!selectedCropId) return;
        fetch('api/face-crops/' + selectedCropId + '/assign', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ person_id: personId }),
        })
            .then(function (r) {
                if (r.ok) location.reload();
                else r.json().then(function (d) { alert('Error: ' + (d.detail || 'Unknown')); });
            });
    };

    window.assignCropNewPerson = function () {
        var name = (document.getElementById('new-crop-name') || {}).value || '';
        name = name.trim();
        if (!name || !selectedCropId) return;
        fetch('api/face-crops/' + selectedCropId + '/assign', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name }),
        })
            .then(function (r) {
                if (r.ok) location.reload();
                else r.json().then(function (d) { alert('Error: ' + (d.detail || 'Unknown')); });
            });
    };

    window.dismissCrop = function () {
        if (!selectedCropId) return;
        fetch('api/face-crops/' + selectedCropId + '/dismiss', { method: 'POST' })
            .then(function (r) {
                if (r.ok) location.reload();
            });
    };
});
```

- [ ] **Step 3: Lint + type check**

```bash
flake8 doorbell-addon/src/ --count --select=E9,F63,F7,F82 --show-source --statistics
mypy doorbell-addon/src/ --config-file doorbell-addon/mypy.ini
```

- [ ] **Step 4: Commit**

```bash
git add doorbell-addon/web/templates/base.html doorbell-addon/web/static/js/persons.js
git commit -m "feat: add nav badge span and persons.js global badge polling"
```

---

### Task 11: Two-tab Persons page (`persons.html`)

**Files:**
- Modify: `doorbell-addon/web/templates/persons.html`

- [ ] **Step 1: Rewrite `persons.html`**

Replace the entire contents of `doorbell-addon/web/templates/persons.html` with:
```html
{% extends "base.html" %}

{% block title %}Persons — WhoRang{% endblock %}

{% block content %}
<div class="mb-4">
    <h1 class="wr-page-title">Persons</h1>
    <p class="wr-page-sub">Manage faces for doorbell recognition</p>
</div>

{% if not settings.face_recognition_enabled %}
<div class="alert alert-warning mb-3" style="font-size:13px">
    <i class="bi bi-exclamation-triangle-fill"></i>
    Face recognition is disabled — <a href="settings">enable it in Settings</a>.
</div>
{% endif %}

<!-- Tab bar -->
<div id="persons-tabs" style="display:flex;border-bottom:1px solid #333;margin-bottom:16px">
    <div data-tab="known"
         style="padding:10px 16px;font-size:13px;font-weight:600;cursor:pointer;border-bottom:2px solid transparent">
        Known
        <span style="background:#38bdf820;color:#38bdf8;border-radius:10px;
                     padding:1px 7px;font-size:11px;margin-left:4px">
            {{ persons | length }}
        </span>
    </div>
    <div data-tab="unrecognised"
         style="padding:10px 16px;font-size:13px;color:#888;cursor:pointer;border-bottom:2px solid transparent">
        Unrecognised
        <span id="unrecognised-tab-badge"
              style="background:#fb923c20;color:#fb923c;border-radius:10px;
                     padding:1px 7px;font-size:11px;margin-left:4px">0</span>
    </div>
</div>

<!-- Known tab pane -->
<div data-pane="known">
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">

        {% for person in persons %}
        <div id="person-card-{{ person.id }}"
             style="background:#1c1c1f;border-radius:8px;padding:12px;border:1px solid #333">
            <!-- Avatar + name row -->
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
                <img src="api/persons/{{ person.id }}/thumbnail"
                     style="width:40px;height:40px;border-radius:50%;object-fit:cover;
                            border:2px solid #38bdf8;flex-shrink:0"
                     onerror="this.outerHTML='<div style=\'width:40px;height:40px;border-radius:50%;background:#6c757d;border:2px solid #38bdf8;flex-shrink:0;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:bold\'>{{ person.name[0]|upper }}</div>'">
                <div style="flex:1;min-width:0">
                    <div id="person-name-{{ person.id }}"
                         style="font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
                        {{ person.name }}
                    </div>
                    <div style="font-size:10px;color:#555" id="sample-count-{{ person.id }}">
                        — samples
                    </div>
                </div>
                <button onclick="deletePerson({{ person.id }}, '{{ person.name|replace("'", "\\'") }}')"
                        style="background:transparent;border:none;color:#555;cursor:pointer;font-size:12px"
                        title="Delete person">🗑</button>
                <span class="rename-btn" data-person-id="{{ person.id }}"
                      style="font-size:10px;color:#555;cursor:pointer" title="Rename">✏</span>
            </div>
            <!-- Sample strip (populated by JS) -->
            <div id="sample-strip-{{ person.id }}" style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:6px"></div>
            {% if settings.face_recognition_enabled %}
            <div style="font-size:10px;color:#fb923c" id="accuracy-hint-{{ person.id }}" style="display:none">
                ⚠ More samples improve accuracy
            </div>
            {% endif %}
        </div>
        {% endfor %}

        <!-- Add new person card -->
        {% if settings.face_recognition_enabled %}
        <div style="background:#1c1c1f;border-radius:8px;padding:12px;border:1px dashed #444;
                    display:flex;flex-direction:column;gap:8px">
            <div style="font-size:13px;font-weight:600;color:#888">
                <i class="bi bi-person-plus-fill"></i> Add person
            </div>
            <input id="new-person-name" type="text" placeholder="Name"
                   style="background:#111;border:1px solid #444;border-radius:4px;
                          padding:4px 8px;font-size:12px;color:#e5e7eb;width:100%">
            <input id="new-person-photo" type="file" accept="image/*"
                   style="font-size:11px;color:#888">
            <div id="add-person-status" style="font-size:11px;min-height:16px"></div>
            <button onclick="addPerson()"
                    style="background:#38bdf820;border:1px solid #38bdf860;border-radius:6px;
                           padding:5px 10px;font-size:12px;color:#38bdf8;cursor:pointer;width:100%">
                Add
            </button>
        </div>
        {% endif %}
    </div>
</div>

<!-- Unrecognised tab pane -->
<div data-pane="unrecognised" style="display:none">
    <div id="crops-grid"
         style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px">
        <p style="color:#666;font-size:13px">Loading…</p>
    </div>

    <!-- Action panel (hidden until a crop is selected) -->
    <div id="crop-action-panel" style="display:none;background:#242428;border-radius:8px;
         padding:14px;border:1px solid #38bdf840">
        <div style="font-size:12px;color:#aaa;margin-bottom:10px">
            Assign this face to:
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
            <span style="font-size:11px;color:#888">Existing:</span>
            {% for person in persons %}
            <button onclick="assignCropToPerson({{ person.id }})"
                    style="background:#38bdf820;border:1px solid #38bdf860;border-radius:20px;
                           padding:4px 10px;font-size:11px;color:#38bdf8;cursor:pointer">
                {{ person.name }}
            </button>
            {% endfor %}
            <div style="width:1px;height:24px;background:#333;margin:0 4px"></div>
            <input id="new-crop-name" placeholder="New name…"
                   style="background:#111;border:1px solid #444;border-radius:4px;
                          padding:4px 8px;font-size:11px;color:#e5e7eb;width:110px">
            <button onclick="assignCropNewPerson()"
                    style="background:#38bdf820;border:1px solid #38bdf860;border-radius:4px;
                           padding:4px 10px;font-size:11px;color:#38bdf8;cursor:pointer">
                Create
            </button>
            <div style="margin-left:auto">
                <button onclick="dismissCrop()"
                        style="background:transparent;border:1px solid #444;border-radius:4px;
                               padding:4px 10px;font-size:11px;color:#666;cursor:pointer">
                    Dismiss
                </button>
            </div>
        </div>
    </div>
</div>

{% endblock %}

{% block extra_scripts %}
<script>
// Populate sample strips for each person card
document.addEventListener('DOMContentLoaded', function () {
    {% for person in persons %}
    (function () {
        var pid = {{ person.id }};
        fetch('api/persons/' + pid)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var p = (data.persons || []).find(function (x) { return x.id === pid; });
                if (!p) return;
                var strip = document.getElementById('sample-strip-' + pid);
                var countEl = document.getElementById('sample-count-' + pid);
                var hint = document.getElementById('accuracy-hint-' + pid);
                if (countEl) countEl.textContent = p.sample_count + ' sample' + (p.sample_count !== 1 ? 's' : '');
                if (hint) hint.style.display = p.sample_count === 1 ? '' : 'none';
                if (!strip) return;
                strip.innerHTML = '';
                (p.samples || []).forEach(function (s) {
                    var wrap = document.createElement('div');
                    wrap.style.cssText = 'position:relative';
                    wrap.innerHTML =
                        '<img src="' + s.thumbnail_path + '" ' +
                        'style="width:34px;height:34px;border-radius:4px;border:1px solid #38bdf860;object-fit:cover" ' +
                        'onerror="this.style.background=\'#333\'">' +
                        '<div onclick="deleteSample(' + pid + ',' + s.id + ')" ' +
                        'style="position:absolute;top:-4px;right:-4px;background:#333;border-radius:50%;' +
                        'width:14px;height:14px;font-size:9px;display:flex;align-items:center;' +
                        'justify-content:center;cursor:pointer;color:#aaa">✕</div>';
                    strip.appendChild(wrap);
                });
                // Add sample button
                var addBtn = document.createElement('div');
                addBtn.onclick = function () { addSample(pid); };
                addBtn.style.cssText = 'width:34px;height:34px;border-radius:4px;border:1px dashed #38bdf860;' +
                    'display:flex;align-items:center;justify-content:center;color:#38bdf8;font-size:18px;cursor:pointer';
                addBtn.textContent = '+';
                strip.appendChild(addBtn);
            })
            .catch(function () {});
    })();
    {% endfor %}

    // Update unrecognised tab badge
    fetch('api/face-crops?count_only=true')
        .then(function (r) { return r.json(); })
        .then(function (d) {
            var el = document.getElementById('unrecognised-tab-badge');
            if (el) el.textContent = d.count || 0;
        })
        .catch(function () {});
});
</script>
{% endblock %}
```

- [ ] **Step 2: Update `/persons` route in `app.py`** to pass persons list to template

The existing `/persons` route already passes `persons` — verify it returns the right data:
```python
@app.get("/persons", response_class=HTMLResponse)
async def persons_page(request: Request):
    """Known persons page."""
    persons = db.get_persons()
    return templates.TemplateResponse(
        "persons.html",
        {"request": request, "persons": persons, "settings": settings},
    )
```
This is already correct. No changes needed.

- [ ] **Step 3: Manual smoke test**

```bash
# Start the app locally (or in Docker) and verify:
# 1. /persons page loads with Known and Unrecognised tabs
# 2. Known tab shows persons with sample strips
# 3. Unrecognised tab shows face crop grid (or "No unrecognised faces" if empty)
# 4. Nav badge appears/hides correctly
```

- [ ] **Step 4: Lint + type check**

```bash
flake8 doorbell-addon/src/ --count --select=E9,F63,F7,F82 --show-source --statistics
mypy doorbell-addon/src/ --config-file doorbell-addon/mypy.ini
```

- [ ] **Step 5: Commit**

```bash
git add doorbell-addon/web/templates/persons.html
git commit -m "feat: rewrite persons.html with two-tab Known/Unrecognised UI"
```

---

### Task 12: Version bump + Docker build + release

**Files:**
- Modify: `doorbell-addon/src/config.py`
- Modify: `doorbell-addon/config.yaml`
- Modify: `doorbell-addon/build.yaml`
- Modify: `doorbell-addon/requirements.txt`

- [ ] **Step 1: Bump version to 1.0.138 in all four files**

`doorbell-addon/src/config.py` — change line 38:
```python
    app_version: ClassVar[str] = "1.0.138"
```

`doorbell-addon/config.yaml` — change line 3:
```yaml
version: "1.0.138"
```

`doorbell-addon/build.yaml` — update both version references:
```yaml
org.opencontainers.image.version: "1.0.138"
# and:
DOORBELL_VERSION: "1.0.138"
```

`doorbell-addon/requirements.txt` — change last line:
```
# Version: 1.0.138
```

- [ ] **Step 2: Run all tests one final time**

```bash
cd doorbell-addon && python -m pytest tests/ -v
```

- [ ] **Step 3: Lint + type check**

```bash
flake8 doorbell-addon/src/ --count --select=E9,F63,F7,F82 --show-source --statistics
mypy doorbell-addon/src/ --config-file doorbell-addon/mypy.ini
```

- [ ] **Step 4: Docker build (local verification)**

```bash
cd doorbell-addon && docker build \
  --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:bookworm \
  --build-arg DOORBELL_VERSION=1.0.138 \
  -t whorang-test .
```
Expected: build completes without error.

- [ ] **Step 5: Smoke test the Docker image**

```bash
docker run -d --name whorang-smoke \
  -e STORAGE_PATH=/tmp/doorbell \
  -e FACE_RECOGNITION_ENABLED=false \
  -p 8099:8099 whorang-test

sleep 5
curl -sf http://localhost:8099/health | python3 -m json.tool
curl -sf http://localhost:8099/api/persons | python3 -m json.tool
curl -sf http://localhost:8099/api/face-crops | python3 -m json.tool
docker stop whorang-smoke && docker rm whorang-smoke
```
Expected: `/health` → 200, `/api/persons` → `{"persons":[]}`, `/api/face-crops` → `{"crops":[]}`

- [ ] **Step 6: Commit + tag**

```bash
git add doorbell-addon/src/config.py doorbell-addon/config.yaml \
        doorbell-addon/build.yaml doorbell-addon/requirements.txt
git commit -m "Release v1.0.138 - Face/person management with multi-sample support"
git tag v1.0.138
git push && git push --tags
```
