"""Database models and operations for the doorbell addon."""

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

import structlog

from .config import settings

logger = structlog.get_logger()


@dataclass
class DoorbellEvent:
    """Doorbell event model."""

    id: Optional[int] = None
    timestamp: Optional[datetime] = None
    image_path: str = ""
    ai_message: Optional[str] = None
    weather_condition: Optional[str] = None
    weather_temperature: Optional[float] = None
    weather_humidity: Optional[float] = None


# Columns returned by all SELECT queries on doorbell_events
_EVENT_COLUMNS = (
    "id, timestamp, image_path, ai_message, "
    "weather_condition, weather_temperature, weather_humidity"
)


class DatabaseManager:
    """Database manager for SQLite operations."""

    def __init__(self):
        self.db_path = settings.database_path
        self._init_database()

    def _init_database(self):
        """Initialize the database with required tables."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS doorbell_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    image_path TEXT NOT NULL,
                    ai_message TEXT,
                    weather_condition TEXT,
                    weather_temperature REAL,
                    weather_humidity REAL
                )
            """
            )

            for col, col_type in [
                ("ai_message", "TEXT"),
                ("weather_condition", "TEXT"),
                ("weather_temperature", "REAL"),
                ("weather_humidity", "REAL"),
            ]:
                try:
                    conn.execute(
                        f"ALTER TABLE doorbell_events ADD COLUMN {col} {col_type}"
                    )
                    conn.commit()
                except sqlite3.OperationalError:
                    pass

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_events_timestamp
                ON doorbell_events (timestamp)
            """
            )
            conn.commit()

    def add_doorbell_event(
        self,
        image_path: str,
        ai_message: Optional[str] = None,
        weather_condition: Optional[str] = None,
        weather_temperature: Optional[float] = None,
        weather_humidity: Optional[float] = None,
    ) -> DoorbellEvent:
        """Add a new doorbell event."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO doorbell_events
                   (image_path, ai_message, weather_condition, weather_temperature, weather_humidity)
                   VALUES (?, ?, ?, ?, ?)""",
                (image_path, ai_message, weather_condition, weather_temperature, weather_humidity),
            )
            event_id = cursor.lastrowid
            conn.commit()

            return DoorbellEvent(
                id=event_id,
                timestamp=datetime.now(),
                image_path=image_path,
                ai_message=ai_message,
                weather_condition=weather_condition,
                weather_temperature=weather_temperature,
                weather_humidity=weather_humidity,
            )

    def get_doorbell_events(
        self, limit: int = 100, offset: int = 0
    ) -> List[DoorbellEvent]:
        """Get doorbell events with pagination."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f"SELECT {_EVENT_COLUMNS} FROM doorbell_events"
                " ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            return [_row_to_event(row) for row in cursor.fetchall()]

    def get_doorbell_event(self, event_id: int) -> Optional[DoorbellEvent]:
        """Get a single doorbell event by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f"SELECT {_EVENT_COLUMNS} FROM doorbell_events WHERE id = ?",
                (event_id,),
            )
            row = cursor.fetchone()
            return _row_to_event(row) if row else None

    def get_event_count(self) -> int:
        """Return total number of doorbell events (fast COUNT query)."""
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM doorbell_events"
            ).fetchone()[0]

    def get_last_event(self) -> Optional[DoorbellEvent]:
        """Return the most recent doorbell event."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f"SELECT {_EVENT_COLUMNS} FROM doorbell_events"
                " ORDER BY timestamp DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return _row_to_event(row) if row else None

    def update_event_comment(self, event_id: int, comment: Optional[str]) -> None:
        """Update the comment/ai_message for an event."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE doorbell_events SET ai_message = ? WHERE id = ?",
                (comment, event_id),
            )
            conn.commit()

    def cleanup_old_events(self) -> int:
        """Clean up old events based on retention policy. Returns deleted count."""
        cutoff_date = datetime.now() - timedelta(days=settings.retention_days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT image_path FROM doorbell_events WHERE timestamp < ?",
                (cutoff_date.isoformat(),),
            )
            image_paths = [row[0] for row in cursor.fetchall()]

            deleted_count = conn.execute(
                "DELETE FROM doorbell_events WHERE timestamp < ?",
                (cutoff_date.isoformat(),),
            ).rowcount
            conn.commit()

        _delete_image_files(image_paths)
        return deleted_count

    def delete_events(self, event_ids: List[int]) -> int:
        """Delete multiple events by their IDs and associated image files."""
        if not event_ids:
            return 0

        placeholders = ",".join("?" * len(event_ids))
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"SELECT image_path FROM doorbell_events WHERE id IN ({placeholders})",
                event_ids,
            )
            image_paths = [row[0] for row in cursor.fetchall()]

            deleted_count = conn.execute(
                f"DELETE FROM doorbell_events WHERE id IN ({placeholders})",
                event_ids,
            ).rowcount
            conn.commit()

        _delete_image_files(image_paths)
        return deleted_count


# ── Module-level helpers ──────────────────────────────────────────────────────


def _row_to_event(row: sqlite3.Row) -> DoorbellEvent:
    return DoorbellEvent(
        id=row["id"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        image_path=row["image_path"],
        ai_message=row["ai_message"],
        weather_condition=row["weather_condition"],
        weather_temperature=row["weather_temperature"],
        weather_humidity=row["weather_humidity"],
    )


def _delete_image_files(image_paths: List[str]) -> None:
    for image_path in image_paths:
        try:
            os.remove(image_path)
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error("Error deleting image", path=image_path, error=str(e))


# Global database instance
db = DatabaseManager()
