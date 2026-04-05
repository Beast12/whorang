# New Sensors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three new HA sensors — `sensor.doorbell_today_count`, `sensor.doorbell_last_weather`, and `sensor.doorbell_last_visitor` (face recognition only) — updating on every ring.

**Architecture:** Add `get_today_event_count()` to `database.py`, then extend `update_sensors()` in `ha_integration.py` to push the three new sensors. `last_visitor` is only registered when `settings.face_recognition_enabled` is true. All data comes from existing DB queries — no new tables or columns.

**Tech Stack:** Python, SQLite, existing HA sensor push pattern (`ha_api.update_sensor`)

---

## Files

| File | Change |
|------|--------|
| `doorbell-addon/src/database.py` | Add `get_today_event_count()` method |
| `doorbell-addon/src/ha_integration.py` | Push 3 new sensors in `update_sensors()` |
| `README.md` | Add new sensors to the sensor table |
| `doorbell-addon/DOCS.md` | Add new sensors to the sensor list |
| `doorbell-addon/CHANGELOG.md` | Add v1.0.162 entry |
| `doorbell-addon/config.yaml` | Bump to 1.0.162 |
| `doorbell-addon/build.yaml` | Bump to 1.0.162 |
| `doorbell-addon/requirements.txt` | Bump version comment to 1.0.162 |
| `doorbell-addon/src/config.py` | Bump app_version to 1.0.162 |

---

## Task 1: Add `get_today_event_count()` to database.py

**Files:**
- Modify: `doorbell-addon/src/database.py` (after `get_event_count()` at line ~415)

- [ ] **Step 1: Add the method**

In `doorbell-addon/src/database.py`, add this method immediately after `get_event_count()`:

```python
    def get_today_event_count(self) -> int:
        """Return number of doorbell events recorded today (since midnight local time)."""
        today_midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM doorbell_events WHERE timestamp >= ?",
                (today_midnight.isoformat(),),
            ).fetchone()[0]
```

- [ ] **Step 2: Commit**

```bash
git add doorbell-addon/src/database.py
git commit -m "feat: add get_today_event_count() to database"
```

---

## Task 2: Push new sensors in `update_sensors()`

**Files:**
- Modify: `doorbell-addon/src/ha_integration.py`

The current `update_sensors()` method fetches `last_event` and `total_events` then pushes three sensors. Extend it to also push `sensor.doorbell_today_count`, `sensor.doorbell_last_weather`, and (conditionally) `sensor.doorbell_last_visitor`.

**face_data JSON structure** (for reference): array of `{"name": str, "bbox": [...], "score": float, "det_score": float}`. `name` is `"Unknown"` for unmatched faces. A "known" visitor is any entry where `name != "Unknown"`.

- [ ] **Step 1: Replace the `update_sensors()` method**

Replace the entire `update_sensors` method with:

```python
    async def update_sensors(self):
        """Update all sensor states."""
        try:
            from .database import db

            last_event = db.get_last_event()
            total_events = db.get_event_count()
            today_count = db.get_today_event_count()
            last_event_time = last_event.timestamp.isoformat() if last_event else "unknown"

            person_detected = (
                last_event is not None
                and (datetime.now() - last_event.timestamp).total_seconds()
                < _PERSON_DETECTED_THRESHOLD_SECS
            )

            # Build last-event attributes for automations
            if last_event:
                last_event_attrs = {
                    "friendly_name": "Doorbell Last Event",
                    "icon": "mdi:doorbell-video",
                    "device_class": "timestamp",
                    "event_id": last_event.id,
                    "description": last_event.ai_message or "",
                }
            else:
                last_event_attrs = {
                    "friendly_name": "Doorbell Last Event",
                    "icon": "mdi:doorbell-video",
                    "device_class": "timestamp",
                    "event_id": None,
                    "description": "",
                }

            # Build weather state string from last event
            if last_event and last_event.weather_condition:
                if last_event.weather_temperature is not None:
                    weather_state = f"{last_event.weather_condition}, {last_event.weather_temperature:.0f}°C"
                else:
                    weather_state = last_event.weather_condition
            else:
                weather_state = "unknown"

            # Build last visitor name from face_data JSON
            last_visitor = None
            if settings.face_recognition_enabled and last_event and last_event.face_data:
                import json as _json
                faces = _json.loads(last_event.face_data)
                known = [f["name"] for f in faces if f.get("name") and f["name"] != "Unknown"]
                last_visitor = known[0] if known else "Unknown"

            sensors = [
                self.ha_api.update_sensor(
                    "sensor.doorbell_last_event",
                    last_event_time,
                    last_event_attrs,
                ),
                self.ha_api.update_sensor(
                    "sensor.doorbell_total_events",
                    total_events,
                    {"friendly_name": "Doorbell Total Events", "icon": "mdi:counter", "unit_of_measurement": "events"},
                ),
                self.ha_api.update_sensor(
                    "sensor.doorbell_today_count",
                    today_count,
                    {"friendly_name": "Doorbell Today", "icon": "mdi:calendar-today", "unit_of_measurement": "events"},
                ),
                self.ha_api.update_sensor(
                    "sensor.doorbell_last_weather",
                    weather_state,
                    {"friendly_name": "Doorbell Last Weather", "icon": "mdi:weather-partly-cloudy"},
                ),
                self.ha_api.update_sensor(
                    "binary_sensor.doorbell_person_detected",
                    "on" if person_detected else "off",
                    {"friendly_name": "Doorbell Person Detected", "device_class": "occupancy", "icon": "mdi:motion-sensor"},
                ),
            ]

            if last_visitor is not None:
                sensors.append(
                    self.ha_api.update_sensor(
                        "sensor.doorbell_last_visitor",
                        last_visitor,
                        {"friendly_name": "Doorbell Last Visitor", "icon": "mdi:account"},
                    )
                )

            await asyncio.gather(*sensors)
            logger.debug("Sensors updated successfully")

        except Exception as e:
            logger.error("Failed to update sensors", error=str(e))
```

- [ ] **Step 2: Commit**

```bash
git add doorbell-addon/src/ha_integration.py
git commit -m "feat: add doorbell_today_count, doorbell_last_weather, doorbell_last_visitor sensors"
```

---

## Task 3: Update README.md and DOCS.md

**Files:**
- Modify: `README.md`
- Modify: `doorbell-addon/DOCS.md`

- [ ] **Step 1: Update sensor table in `README.md`**

Find and replace the sensor table:

```markdown
| Sensor | Description |
|--------|-------------|
| `sensor.doorbell_last_event` | Timestamp of the most recent ring (attributes: `event_id`, `description`) |
| `sensor.doorbell_total_events` | Total number of stored rings |
| `binary_sensor.doorbell_person_detected` | On for 30 s after a ring |
```

Replace with:

```markdown
| Sensor | Description |
|--------|-------------|
| `sensor.doorbell_last_event` | Timestamp of the most recent ring (attributes: `event_id`, `description`) |
| `sensor.doorbell_total_events` | Total number of stored rings |
| `sensor.doorbell_today_count` | Number of rings recorded today (resets at midnight) |
| `sensor.doorbell_last_weather` | Weather at the time of the last ring (e.g. `"sunny, 18°C"`) |
| `binary_sensor.doorbell_person_detected` | On for 30 s after a ring |
| `sensor.doorbell_last_visitor` | Name of the last recognised visitor — only created when face recognition is enabled |
```

- [ ] **Step 2: Update sensor list in `DOCS.md`**

Find and replace the sensor list:

```markdown
- `sensor.doorbell_last_event` — timestamp of last ring; attributes: `event_id`, `description`
- `sensor.doorbell_total_events` — total rings recorded
- `binary_sensor.doorbell_person_detected` — on for 30 s after a ring
```

Replace with:

```markdown
- `sensor.doorbell_last_event` — timestamp of last ring; attributes: `event_id`, `description`
- `sensor.doorbell_total_events` — total rings recorded
- `sensor.doorbell_today_count` — rings recorded today (resets at midnight)
- `sensor.doorbell_last_weather` — weather at the time of the last ring (e.g. `"sunny, 18°C"`)
- `binary_sensor.doorbell_person_detected` — on for 30 s after a ring
- `sensor.doorbell_last_visitor` — name of the last recognised visitor; only created when face recognition is enabled
```

- [ ] **Step 3: Commit**

```bash
git add README.md doorbell-addon/DOCS.md
git commit -m "docs: add new sensors to README and DOCS"
```

---

## Task 4: Version bump and release

**Files:**
- Modify: `doorbell-addon/CHANGELOG.md`
- Modify: `doorbell-addon/config.yaml`
- Modify: `doorbell-addon/build.yaml`
- Modify: `doorbell-addon/requirements.txt`
- Modify: `doorbell-addon/src/config.py`

- [ ] **Step 1: Add CHANGELOG entry**

In `doorbell-addon/CHANGELOG.md`, add before `## [1.0.161]`:

```markdown
## [1.0.162] - 2026-04-05

### Added
- `sensor.doorbell_today_count` — rings recorded today, resets at midnight
- `sensor.doorbell_last_weather` — weather condition and temperature at the time of the last ring (e.g. `"sunny, 18°C"`)
- `sensor.doorbell_last_visitor` — name of the last recognised visitor; only created when face recognition is enabled

```

- [ ] **Step 2: Bump version in all four files**

`doorbell-addon/config.yaml`:
```yaml
version: "1.0.162"
```

`doorbell-addon/build.yaml` (both occurrences):
```yaml
  org.opencontainers.image.version: "1.0.162"
...
  DOORBELL_VERSION: "1.0.162"
```

`doorbell-addon/requirements.txt`:
```
# Version: 1.0.162
```

`doorbell-addon/src/config.py`:
```python
    app_version: ClassVar[str] = "1.0.162"
```

`README.md` version badge:
```markdown
[![Version](https://img.shields.io/badge/version-1.0.162-blue.svg)](https://github.com/Beast12/whorang/releases)
```

- [ ] **Step 3: Commit, tag, and push**

```bash
git add doorbell-addon/CHANGELOG.md doorbell-addon/config.yaml doorbell-addon/build.yaml doorbell-addon/requirements.txt doorbell-addon/src/config.py README.md
git commit -m "chore: release v1.0.162 — three new HA sensors"
git tag v1.0.162
git push origin main
git push origin v1.0.162
```
