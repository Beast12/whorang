"""Database models and operations for the doorbell face recognition addon."""

import base64
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

import numpy as np
from cryptography.fernet import Fernet

from .config import settings


@dataclass
class Person:
    """Person model for face recognition."""

    id: Optional[int] = None
    name: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class FaceEncoding:
    """Face encoding model."""

    id: Optional[int] = None
    person_id: int = 0
    encoding: Optional[np.ndarray] = None
    confidence: float = 0.0
    created_at: Optional[datetime] = None
    source_image_path: Optional[str] = None
    thumbnail_path: Optional[str] = None


@dataclass
class DoorbellEvent:
    """Doorbell event model."""

    id: Optional[int] = None
    timestamp: Optional[datetime] = None
    image_path: str = ""
    person_id: Optional[int] = None
    confidence: Optional[float] = None
    is_known: bool = False
    processed: bool = False
    ai_message: Optional[str] = None
    weather_condition: Optional[str] = None
    weather_temperature: Optional[float] = None
    weather_humidity: Optional[float] = None
    face_top: Optional[int] = None
    face_right: Optional[int] = None
    face_bottom: Optional[int] = None
    face_left: Optional[int] = None


class DatabaseManager:
    """Database manager for SQLite operations."""

    def __init__(self):
        self.db_path = settings.database_path
        self.encryption_key = (
            self._get_or_create_encryption_key()
            if settings.database_encryption
            else None
        )
        self._init_database()

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for database."""
        key_path = os.path.join(settings.storage_path, "database", ".key")
        os.makedirs(os.path.dirname(key_path), exist_ok=True)

        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_path, "wb") as f:
                f.write(key)
            os.chmod(key_path, 0o600)
            return key

    def _encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data."""
        if not self.encryption_key:
            return data

        fernet = Fernet(self.encryption_key)
        encrypted = fernet.encrypt(data.encode())
        return base64.b64encode(encrypted).decode()

    def _decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        if not self.encryption_key:
            return encrypted_data

        fernet = Fernet(self.encryption_key)
        encrypted_bytes = base64.b64decode(encrypted_data.encode())
        decrypted = fernet.decrypt(encrypted_bytes)
        return decrypted.decode()

    def _init_database(self):
        """Initialize the database with required tables."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            # Create persons table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS persons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Create face_encodings table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS face_encodings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_id INTEGER NOT NULL,
                    encoding TEXT NOT NULL,
                    confidence REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (person_id) REFERENCES persons (id) ON DELETE CASCADE
                )
            """
            )

            # Create doorbell_events table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS doorbell_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    image_path TEXT NOT NULL,
                    person_id INTEGER,
                    confidence REAL,
                    is_known BOOLEAN DEFAULT FALSE,
                    processed BOOLEAN DEFAULT FALSE,
                    ai_message TEXT,
                    weather_condition TEXT,
                    weather_temperature REAL,
                    weather_humidity REAL,
                    FOREIGN KEY (person_id) REFERENCES persons (id) ON DELETE SET NULL
                )
            """
            )

            # Add ai_message column if it doesn't exist (migration for existing databases)
            try:
                conn.execute("ALTER TABLE doorbell_events ADD COLUMN ai_message TEXT")
                conn.commit()
            except sqlite3.OperationalError:
                # Column already exists, ignore
                pass

            # Add weather columns if they don't exist (migration for existing databases)
            try:
                conn.execute(
                    "ALTER TABLE doorbell_events ADD COLUMN weather_condition TEXT"
                )
                conn.commit()
            except sqlite3.OperationalError:
                pass

            try:
                conn.execute(
                    "ALTER TABLE doorbell_events ADD COLUMN weather_temperature REAL"
                )
                conn.commit()
            except sqlite3.OperationalError:
                pass

            try:
                conn.execute(
                    "ALTER TABLE doorbell_events ADD COLUMN weather_humidity REAL"
                )
                conn.commit()
            except sqlite3.OperationalError:
                pass

            # Add source_image_path and thumbnail_path columns to face_encodings (migration)
            try:
                conn.execute(
                    "ALTER TABLE face_encodings ADD COLUMN source_image_path TEXT"
                )
                conn.commit()
            except sqlite3.OperationalError:
                pass

            try:
                conn.execute(
                    "ALTER TABLE face_encodings ADD COLUMN thumbnail_path TEXT"
                )
                conn.commit()
            except sqlite3.OperationalError:
                pass

            # Add face location columns to doorbell_events (migration)
            try:
                conn.execute("ALTER TABLE doorbell_events ADD COLUMN face_top INTEGER")
                conn.commit()
            except sqlite3.OperationalError:
                pass

            try:
                conn.execute(
                    "ALTER TABLE doorbell_events ADD COLUMN face_right INTEGER"
                )
                conn.commit()
            except sqlite3.OperationalError:
                pass

            try:
                conn.execute(
                    "ALTER TABLE doorbell_events ADD COLUMN face_bottom INTEGER"
                )
                conn.commit()
            except sqlite3.OperationalError:
                pass

            try:
                conn.execute("ALTER TABLE doorbell_events ADD COLUMN face_left INTEGER")
                conn.commit()
            except sqlite3.OperationalError:
                pass

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_events_timestamp
                ON doorbell_events (timestamp)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_events_person
                ON doorbell_events (person_id)
            """
            )

            conn.commit()

    def add_person(self, name: str) -> Person:
        """Add a new person to the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("INSERT INTO persons (name) VALUES (?)", (name,))
            person_id = cursor.lastrowid
            conn.commit()

            return Person(
                id=person_id,
                name=name,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

    def get_person(self, person_id: int) -> Optional[Person]:
        """Get a person by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,))
            row = cursor.fetchone()

            if row:
                return Person(
                    id=row["id"],
                    name=row["name"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
            return None

    def get_all_persons(self) -> List[Person]:
        """Get all persons from the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM persons ORDER BY name")
            rows = cursor.fetchall()

            return [
                Person(
                    id=row["id"],
                    name=row["name"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
                for row in rows
            ]

    def update_person_name(self, person_id: int, new_name: str) -> None:
        """Update a person's name."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE persons SET name = ?, updated_at = ? WHERE id = ?",
                (new_name, datetime.now().isoformat(), person_id),
            )
            conn.commit()

    def delete_person(self, person_id: int) -> None:
        """Delete a person and all their face encodings (cascade)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM persons WHERE id = ?", (person_id,))
            conn.commit()

    def add_face_encoding(
        self,
        person_id: int,
        encoding: np.ndarray,
        confidence: float = 0.0,
        source_image_path: Optional[str] = None,
        thumbnail_path: Optional[str] = None,
    ) -> FaceEncoding:
        """Add a face encoding for a person."""
        encoding_json = json.dumps(encoding.tolist())
        encrypted_encoding = self._encrypt_data(encoding_json)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO face_encodings 
                   (person_id, encoding, confidence, source_image_path, thumbnail_path) 
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    person_id,
                    encrypted_encoding,
                    confidence,
                    source_image_path,
                    thumbnail_path,
                ),
            )
            encoding_id = cursor.lastrowid
            conn.commit()

            return FaceEncoding(
                id=encoding_id,
                person_id=person_id,
                encoding=encoding,
                confidence=confidence,
                created_at=datetime.now(),
                source_image_path=source_image_path,
                thumbnail_path=thumbnail_path,
            )

    def get_face_encodings(self, person_id: Optional[int] = None) -> List[FaceEncoding]:
        """Get face encodings, optionally filtered by person."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if person_id:
                cursor = conn.execute(
                    "SELECT * FROM face_encodings WHERE person_id = ?", (person_id,)
                )
            else:
                cursor = conn.execute("SELECT * FROM face_encodings")

            rows = cursor.fetchall()
            encodings = []

            for row in rows:
                try:
                    decrypted_encoding = self._decrypt_data(row["encoding"])
                    encoding_array = np.array(json.loads(decrypted_encoding))

                    # Handle optional fields that may not exist in older databases
                    source_image_path = None
                    thumbnail_path = None
                    try:
                        source_image_path = row["source_image_path"]
                    except (KeyError, IndexError):
                        pass
                    try:
                        thumbnail_path = row["thumbnail_path"]
                    except (KeyError, IndexError):
                        pass

                    encodings.append(
                        FaceEncoding(
                            id=row["id"],
                            person_id=row["person_id"],
                            encoding=encoding_array,
                            confidence=row["confidence"],
                            created_at=datetime.fromisoformat(row["created_at"]),
                            source_image_path=source_image_path,
                            thumbnail_path=thumbnail_path,
                        )
                    )
                except Exception as e:
                    print(f"Error loading face encoding {row['id']}: {e}")
                    continue

            return encodings

    def delete_face_encoding(self, encoding_id: int) -> None:
        """Delete a specific face encoding."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM face_encodings WHERE id = ?", (encoding_id,))
            conn.commit()

    def add_doorbell_event(
        self,
        image_path: str,
        person_id: Optional[int] = None,
        confidence: Optional[float] = None,
        ai_message: Optional[str] = None,
        weather_condition: Optional[str] = None,
        weather_temperature: Optional[float] = None,
        weather_humidity: Optional[float] = None,
        face_top: Optional[int] = None,
        face_right: Optional[int] = None,
        face_bottom: Optional[int] = None,
        face_left: Optional[int] = None,
    ) -> DoorbellEvent:
        """Add a new doorbell event."""
        is_known = person_id is not None

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO doorbell_events
                   (image_path, person_id, confidence, is_known, processed, ai_message,
                    weather_condition, weather_temperature, weather_humidity,
                    face_top, face_right, face_bottom, face_left)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    image_path,
                    person_id,
                    confidence,
                    is_known,
                    False,
                    ai_message,
                    weather_condition,
                    weather_temperature,
                    weather_humidity,
                    face_top,
                    face_right,
                    face_bottom,
                    face_left,
                ),
            )
            event_id = cursor.lastrowid
            conn.commit()

            return DoorbellEvent(
                id=event_id,
                timestamp=datetime.now(),
                image_path=image_path,
                person_id=person_id,
                confidence=confidence,
                is_known=is_known,
                processed=False,
                ai_message=ai_message,
                weather_condition=weather_condition,
                weather_temperature=weather_temperature,
                weather_humidity=weather_humidity,
                face_top=face_top,
                face_right=face_right,
                face_bottom=face_bottom,
                face_left=face_left,
            )

    def get_doorbell_events(
        self, limit: int = 100, offset: int = 0, person_id: Optional[int] = None
    ) -> List[DoorbellEvent]:
        """Get doorbell events with pagination."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if person_id:
                cursor = conn.execute(
                    """SELECT * FROM doorbell_events
                       WHERE person_id = ?
                       ORDER BY timestamp DESC
                       LIMIT ? OFFSET ?""",
                    (person_id, limit, offset),
                )
            else:
                cursor = conn.execute(
                    """SELECT * FROM doorbell_events
                       ORDER BY timestamp DESC
                       LIMIT ? OFFSET ?""",
                    (limit, offset),
                )

            rows = cursor.fetchall()

            return [
                DoorbellEvent(
                    id=row["id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    image_path=row["image_path"],
                    person_id=row["person_id"],
                    confidence=row["confidence"],
                    is_known=bool(row["is_known"]),
                    processed=bool(row["processed"]),
                    ai_message=row["ai_message"],
                    weather_condition=(
                        row["weather_condition"]
                        if "weather_condition" in row.keys()
                        else None
                    ),
                    weather_temperature=(
                        row["weather_temperature"]
                        if "weather_temperature" in row.keys()
                        else None
                    ),
                    weather_humidity=(
                        row["weather_humidity"]
                        if "weather_humidity" in row.keys()
                        else None
                    ),
                    face_top=row["face_top"] if "face_top" in row.keys() else None,
                    face_right=(
                        row["face_right"] if "face_right" in row.keys() else None
                    ),
                    face_bottom=(
                        row["face_bottom"] if "face_bottom" in row.keys() else None
                    ),
                    face_left=row["face_left"] if "face_left" in row.keys() else None,
                )
                for row in rows
            ]

    def get_doorbell_event(self, event_id: int) -> Optional[DoorbellEvent]:
        """Get a single doorbell event by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute(
                "SELECT * FROM doorbell_events WHERE id = ?", (event_id,)
            )
            row = cursor.fetchone()

            if row:
                return DoorbellEvent(
                    id=row["id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    image_path=row["image_path"],
                    person_id=row["person_id"],
                    confidence=row["confidence"],
                    is_known=bool(row["is_known"]),
                    processed=bool(row["processed"]),
                    ai_message=(
                        row["ai_message"] if "ai_message" in row.keys() else None
                    ),
                    weather_condition=(
                        row["weather_condition"]
                        if "weather_condition" in row.keys()
                        else None
                    ),
                    weather_temperature=(
                        row["weather_temperature"]
                        if "weather_temperature" in row.keys()
                        else None
                    ),
                    weather_humidity=(
                        row["weather_humidity"]
                        if "weather_humidity" in row.keys()
                        else None
                    ),
                    face_top=row["face_top"] if "face_top" in row.keys() else None,
                    face_right=(
                        row["face_right"] if "face_right" in row.keys() else None
                    ),
                    face_bottom=(
                        row["face_bottom"] if "face_bottom" in row.keys() else None
                    ),
                    face_left=row["face_left"] if "face_left" in row.keys() else None,
                )
            return None

    def cleanup_old_events(self):
        """Clean up old events based on retention policy."""
        cutoff_date = datetime.now() - timedelta(days=settings.retention_days)

        with sqlite3.connect(self.db_path) as conn:
            # Get image paths of events to be deleted
            cursor = conn.execute(
                "SELECT image_path FROM doorbell_events WHERE timestamp < ?",
                (cutoff_date.isoformat(),),
            )
            image_paths = [row[0] for row in cursor.fetchall()]

            # Delete old events
            conn.execute(
                "DELETE FROM doorbell_events WHERE timestamp < ?",
                (cutoff_date.isoformat(),),
            )
            conn.commit()

            # Delete associated image files
            for image_path in image_paths:
                try:
                    if os.path.exists(image_path):
                        os.remove(image_path)
                except Exception as e:
                    print(f"Error deleting image {image_path}: {e}")

    def delete_events(self, event_ids: List[int]) -> int:
        """Delete multiple events by their IDs and associated image files."""
        if not event_ids:
            return 0

        with sqlite3.connect(self.db_path) as conn:
            # Get image paths of events to be deleted
            placeholders = ",".join("?" * len(event_ids))
            cursor = conn.execute(
                f"SELECT image_path FROM doorbell_events WHERE id IN ({placeholders})",
                event_ids,
            )
            image_paths = [row[0] for row in cursor.fetchall()]

            # Delete events from database
            deleted_count = conn.execute(
                f"DELETE FROM doorbell_events WHERE id IN ({placeholders})",
                event_ids,
            ).rowcount
            conn.commit()

            # Delete associated image files
            for image_path in image_paths:
                try:
                    if os.path.exists(image_path):
                        os.remove(image_path)
                except Exception as e:
                    print(f"Error deleting image {image_path}: {e}")

            return deleted_count

    def update_event_person(self, event_id: int, person_id: int, confidence: float):
        """Update an event with person identification."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE doorbell_events
                   SET person_id = ?, confidence = ?, is_known = TRUE, processed = TRUE
                   WHERE id = ?""",
                (person_id, confidence, event_id),
            )
            conn.commit()


# Global database instance
db = DatabaseManager()
