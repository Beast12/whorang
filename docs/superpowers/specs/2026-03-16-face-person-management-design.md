# Face / Person Management — Design Spec

**Date:** 2026-03-16
**Status:** Approved

---

## Overview

WhoRang can detect and identify faces at the doorbell. This feature makes it easy to name unrecognised faces, add multiple photo samples per person to improve recognition accuracy, rename, delete, and dismiss faces.

Recognition happens entirely locally; no cloud services are involved.

---

## 1. Data Model

### `known_persons` table (existing, modified)

The `embedding BLOB NOT NULL` column is removed. Change the `CREATE TABLE IF NOT EXISTS known_persons` statement in `_init_database()` to the new schema (no `embedding` column) so fresh installs use the correct schema:

```sql
CREATE TABLE IF NOT EXISTS known_persons (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    thumbnail_path TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Migration for existing installs**

**Ordering requirement:** All DDL and the migration block must execute within the **same SQLite connection** (the existing `_init_database()` uses one connection throughout — preserve this). The migration block must run AFTER both `person_embeddings` AND `face_crops` tables have been created (i.e., after all three `CREATE TABLE IF NOT EXISTS` statements). Only run if `PRAGMA table_info(known_persons)` returns a row with `name == "embedding"`.

```sql
-- person_embeddings and face_crops tables already exist at this point

-- Step 1: copy embeddings into person_embeddings BEFORE dropping known_persons
INSERT INTO person_embeddings (person_id, embedding, thumbnail_path, created_at)
    SELECT id, embedding, thumbnail_path, created_at
    FROM known_persons
    WHERE embedding IS NOT NULL;

-- Step 2: rebuild known_persons without the embedding column
CREATE TABLE known_persons_new (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    thumbnail_path TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO known_persons_new (id, name, thumbnail_path, created_at)
    SELECT id, name, thumbnail_path, created_at FROM known_persons;
DROP TABLE known_persons;
ALTER TABLE known_persons_new RENAME TO known_persons;
```

Migrated `person_embeddings` rows inherit the existing `thumbnail_path` as-is (file already exists on disk; no rename needed).

### `person_embeddings` table (new)

```sql
CREATE TABLE IF NOT EXISTS person_embeddings (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id      INTEGER NOT NULL REFERENCES known_persons(id) ON DELETE CASCADE,
    embedding      BLOB NOT NULL,
    thumbnail_path TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Thumbnail file naming:** `{persons_path}/{person_id}_{embedding_id}.jpg`

Because `embedding_id` is assigned by SQLite after INSERT, the flow for saving a new sample thumbnail is:
1. Save crop to temp path: `{persons_path}/{person_id}_tmp.jpg`
2. `db.add_person_embedding(person_id, embedding_bytes, thumbnail_path=None)` → `emb_id`
3. Rename file: `{persons_path}/{person_id}_tmp.jpg` → `{persons_path}/{person_id}_{emb_id}.jpg`
4. `db.update_person_embedding_thumbnail(emb_id, final_path)`

**Person avatar** (`known_persons.thumbnail_path`): always stored imperatively via `db.update_person_thumbnail(person_id, path)`. It equals the `thumbnail_path` of the lowest-`id` (oldest) `person_embeddings` row for that person. It is never derived at read time — it is updated eagerly on every operation that adds or removes samples:

- **Add sample:** if current avatar is NULL → call `db.update_person_thumbnail(person_id, new_thumb)`.
- **Remove sample:** if the deleted embedding's `thumbnail_path == known_persons.thumbnail_path` (was the avatar), query the remaining `person_embeddings` for this person ordered by `id ASC LIMIT 1`. If found → `db.update_person_thumbnail(person_id, found_thumb)`; if none → `db.update_person_thumbnail(person_id, None)`.
- **Assign crop (new person):** always call `db.update_person_thumbnail(person_id, new_thumb)` after inserting the first embedding.
- **Person creation (POST /api/persons):** call `db.update_person_thumbnail(person_id, new_thumb)` after inserting the first embedding.

### `face_crops` table (new)

```sql
CREATE TABLE IF NOT EXISTS face_crops (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id       INTEGER NOT NULL REFERENCES doorbell_events(id) ON DELETE CASCADE,
    image_path     TEXT NOT NULL,   -- filesystem path
    dismissed      BOOLEAN NOT NULL DEFAULT 0,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_face_crops_dismissed ON face_crops (dismissed);
```

### `db.add_person` signature change

The existing `db.add_person(name, embedding_bytes, thumbnail_path)` must be changed to `db.add_person(name) -> int` (returns new person id only). Embedding storage is exclusively through `db.add_person_embedding(...)`.

`POST /api/persons` flow (person creation requires an image to seed the first embedding):

1. Validate name (non-empty after strip) → 422 if empty.
2. Save uploaded image to a temp path.
3. `analyze_image(temp_path)` → highest det_score face. If none → delete temp file; return 422 `{"detail": "No face detected in uploaded image"}`.
4. `db.add_person(name)` → `person_id`.
5. Crop thumbnail: temp naming → INSERT `person_embeddings` → rename → UPDATE (see §1).
6. `db.update_person_thumbnail(person_id, final_thumb_path)`.
7. `refresh_embeddings_cache()`.
8. Return 201 with the full person object (same shape as one entry in `GET /api/persons`).

`db.update_person_thumbnail` is an existing method (survives unchanged) — it updates `known_persons.thumbnail_path` for a given person_id.

### New `settings` property

Add to `src/config.py`:

```python
@property
def face_crops_path(self) -> str:
    return os.path.join(self.storage_path, "face_crops")
```

**Both changes must land in the same commit:** `ensure_directories()` in `utils.py` must add `settings.face_crops_path` to its directory list at the same time as the property is added to `config.py`. `ensure_directories()` is called at startup — if the property is missing the service crashes with `AttributeError`.

---

## 2. UI

### Persons page (`/persons`)

**Known tab**

- 3-column card grid. Each card shows:
  - Avatar circle (`thumbnail_path`; grey placeholder if NULL)
  - Name with ✏ inline rename (blur/Enter → `PATCH /api/persons/{id}`; empty string → ignore/revert)
  - Sample count
  - Thumbnail strip: one 34×34 tile per sample, each with ✕ → `DELETE /api/persons/{id}/samples/{emb_id}`
  - `+` dashed tile → file picker → `POST /api/persons/{id}/samples`
  - 🗑 button → `DELETE /api/persons/{id}`
  - Warning when `sample_count == 1`: "⚠ More samples improve accuracy"
- "Add new person" card → name input + file picker → `POST /api/persons`

**Unrecognised tab**

- 4-column grid loaded from `GET /api/face-crops?dismissed=false`
- Select crop → action panel: existing person pills (`POST .../assign` with `{person_id}`), new name input + Create (`POST .../assign` with `{name}`), Dismiss button
- Tab badge: crop count (orange)
- When face recognition disabled: banner "Face recognition is disabled — enable it in Settings" on both tabs

**Nav badge**

- `<span id="unrecognised-count"></span>` placeholder in `base.html` nav link
- `persons.js` is loaded **globally** in `base.html` (before `{% block extra_scripts %}`)
- On every page, `persons.js` polls `GET /api/face-crops?count_only=true` every 30 seconds and updates the span
- When response `count == 0` or face recognition is disabled (check `GET /api/face-recognition/status` once on load), the span is hidden

Loading `persons.js` globally (not just on the persons page) is necessary for the nav badge to update on all pages.

---

## 3. Recognition Logic

### Cache structure change

```python
# Before
_embeddings_cache: Dict[int, np.ndarray]  # {person_id: embedding}

# After
_embeddings_cache: Dict[int, Tuple[int, str, np.ndarray]]
#                       {embedding_id: (person_id, person_name, embedding)}
```

Caching `person_name` avoids DB round-trips during `identify_faces()`.

`_refresh_embeddings_cache_sync()` uses new `db.get_all_embeddings()` (single JOIN query):

```python
def _refresh_embeddings_cache_sync(self) -> None:
    # db.get_all_embeddings() returns List[dict] with keys:
    #   "id" (int, embedding_id), "person_id" (int), "name" (str), "embedding" (bytes)
    cache: Dict[int, Tuple[int, str, Any]] = {}
    for row in db.get_all_embeddings():
        try:
            buf = io.BytesIO(row["embedding"])
            emb = np.load(buf, allow_pickle=False)
            cache[row["id"]] = (row["person_id"], row["name"], emb)
        except Exception as e:
            logger.warning("Failed to load embedding", embedding_id=row["id"], error=str(e))
    self._embeddings_cache = cache
```

### Revised `identify_faces()` logic

With multiple embeddings per person, the result must pick the best-matching person:

```python
def identify_faces(self, faces: List[FaceResult]) -> List[IdentifiedFace]:
    identified = []
    for face in faces:
        norm_emb = face.embedding / (np.linalg.norm(face.embedding) + 1e-10)
        # best_per_person: {person_id: (name, best_score)}
        best_per_person: Dict[int, Tuple[str, float]] = {}
        for emb_id, (person_id, person_name, known_emb) in self._embeddings_cache.items():
            norm_known = known_emb / (np.linalg.norm(known_emb) + 1e-10)
            score = float(np.dot(norm_emb, norm_known))
            if score >= settings.face_recognition_threshold:
                prev = best_per_person.get(person_id)
                if prev is None or score > prev[1]:
                    best_per_person[person_id] = (person_name, score)
        if best_per_person:
            best_person_id = max(best_per_person, key=lambda pid: best_per_person[pid][1])
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

`IdentifiedFace` gains `person_id: Optional[int] = None`.

### Ring handler flow

Crop-saving happens **after** `db.add_doorbell_event()`:

```
1. capture_image() → image_path
2. asyncio.gather(analyze_image(), fetch_weather())
3. identify_faces(raw_faces) → List[IdentifiedFace]
4. build face_data_json
5. db.add_doorbell_event(...) → event_id
6. for idx, face in enumerate(identified) where face.name == "Unknown":
       path = face_recognition_service.save_face_crop(image_path, face.bbox, event_id, idx)
       db.add_face_crop(event_id, path)
7. ha_integration, notifications
```

### `save_face_crop` helper

```python
def save_face_crop(self, image_path: str, bbox: tuple, event_id: int, face_idx: int) -> str:
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

bbox format: `(x, y, w, h)` where `x, y` = top-left corner, consistent with the existing `analyze_image()` return format.

### Assigning a crop to a person

`POST /api/face-crops/{id}/assign` — body: exactly one of `{person_id: N}` or `{name: "Alice"}`. Both/neither → 422.

Error handling and rollback:

| Failure point | Rollback action |
|---|---|
| Step 2: no face detected in crop | Delete newly created person (if `name` was given); return 422 |
| Step 3: thumbnail save / file I/O error | Delete newly created person (if applicable); return 500 |
| Step 4–7: DB error | Delete temp file (if any); delete newly created person (if applicable); return 500 |

Only the `known_persons` row is rolled back on failure — not any partial `person_embeddings` rows (the DB transaction ensures those are not partially committed).

Full flow:

1. Fetch crop; 404 if not found.
2. If `name` given: `db.add_person(name)` → `person_id`. Track `created_person = True`.
3. `analyze_image(crop.image_path)` → highest det_score face. If none: rollback (delete person if `created_person`); return 422.
4. Save thumbnail temp → INSERT `person_embeddings` → rename → UPDATE (see §1 temp naming).
5. If `known_persons.thumbnail_path IS NULL`: `db.update_person_thumbnail(person_id, final_thumb)`.
6. `db.dismiss_face_crop(crop_id)`.
7. `refresh_embeddings_cache()`.
8. Return `{"person_id": ..., "embedding_id": ..., "name": ...}`.

### Adding a sample (Known tab)

`POST /api/persons/{id}/samples` — multipart `image`:

1. 404 if person not found.
2. Save upload to temp.
3. `analyze_image(temp_path)` → highest det_score. None → delete temp; return 422.
4. Save thumbnail: temp → INSERT → rename → UPDATE.
5. Set avatar if NULL.
6. `refresh_embeddings_cache()`.
7. Return `{id, person_id, thumbnail_path: "/api/persons/{id}/samples/{emb_id}/thumbnail", created_at}`.

### Removing a sample

`DELETE /api/persons/{id}/samples/{emb_id}`:

1. Fetch row; 404 if not found or person_id mismatch.
2. Delete file (ignore OS error).
3. `db.delete_person_embedding(emb_id)`.
4. If deleted sample's `thumbnail_path` matches `known_persons.thumbnail_path`: query lowest-id remaining embedding; if found → update avatar; if none → set avatar NULL.
5. `refresh_embeddings_cache()`.
6. Return 204.

### Deleting a person

`DELETE /api/persons/{id}`:

1. `db.get_person_embeddings(person_id)` → collect all `thumbnail_path` values.
2. `db.delete_person(person_id)` (CASCADE removes embedding rows).
3. Delete each thumbnail file (ignore OS errors).
4. `refresh_embeddings_cache()`.
5. Return 204.

### New database methods

```python
db.add_person(name: str) -> int
    # INSERT INTO known_persons (name) VALUES (?) — no embedding_bytes parameter
    # (changed from existing signature add_person(name, embedding_bytes, thumbnail_path))

db.update_person_thumbnail(person_id: int, thumbnail_path: Optional[str]) -> None
    # Existing method — signature updated: thumbnail_path must accept Optional[str] (was str).
    # The SQL is: UPDATE known_persons SET thumbnail_path=? WHERE id=?
    # Passing None sets the column to NULL (avatar reset when all samples removed).

db.get_all_embeddings() -> List[dict]
    # SELECT pe.id, pe.person_id, kp.name, pe.embedding
    # FROM person_embeddings pe JOIN known_persons kp ON pe.person_id = kp.id

db.add_person_embedding(person_id: int, embedding_bytes: bytes, thumbnail_path: Optional[str]) -> int

db.update_person_embedding_thumbnail(emb_id: int, thumbnail_path: str) -> None

db.delete_person_embedding(emb_id: int) -> bool

db.get_person_embeddings(person_id: int) -> List[dict]

db.add_face_crop(event_id: int, image_path: str) -> int

db.dismiss_face_crop(crop_id: int) -> None

db.get_face_crops(dismissed: bool = False) -> List[dict]
    # SELECT fc.*, de.timestamp as event_timestamp
    # FROM face_crops fc JOIN doorbell_events de ON fc.event_id = de.id
    # WHERE fc.dismissed = ?

db.get_face_crop_count(dismissed: bool = False) -> int
```

---

## 4. API

### 503 guard

When `face_recognition_enabled=False`, return 503 `{"detail": "Face recognition is not enabled"}` for:
- `POST /api/persons`
- `POST /api/persons/{id}/samples`
- `POST /api/face-crops/{id}/assign`

All other endpoints function regardless of face recognition state.

### URL vs filesystem path

All `image_path` / `thumbnail_path` values in API responses are **URL paths** (e.g. `/api/persons/1/thumbnail`), not filesystem paths. The URL-to-path transformation happens in the endpoint serializer, not in the DB layer. The DB stores filesystem paths.

### Endpoint specifications

#### `GET /api/persons`

Response 200:
```json
{
  "persons": [
    {
      "id": 1,
      "name": "Alice",
      "thumbnail_path": "/api/persons/1/thumbnail",
      "sample_count": 2,
      "samples": [
        {"id": 5, "thumbnail_path": "/api/persons/1/samples/5/thumbnail", "created_at": "2026-03-16T10:00:00"},
        {"id": 6, "thumbnail_path": "/api/persons/1/samples/6/thumbnail", "created_at": "2026-03-16T11:00:00"}
      ]
    }
  ]
}
```

#### `POST /api/persons`

Request: multipart `name` (non-empty after strip) + `image` (file).
Response 201: same shape as one entry in `GET /api/persons` persons array (includes `samples`).
No `"success"` wrapper. Errors: 422 empty name; 422 no face; 503.

#### `DELETE /api/persons/{id}`

Response 204. 404 if not found.

#### `PATCH /api/persons/{id}`

Request: `{"name": "New Name"}`. Empty string after strip → 422.
Response 200: `{"id": 1, "name": "New Name"}`. 404.

#### `POST /api/persons/{id}/samples`

Request: multipart `image`.
Response 201: `{"id": 7, "person_id": 1, "thumbnail_path": "/api/persons/1/samples/7/thumbnail", "created_at": "..."}`.
Errors: 404/422/503.

#### `DELETE /api/persons/{id}/samples/{emb_id}`

Response 204. 404 if not found or person mismatch.

#### `GET /api/persons/{id}/thumbnail`

Fetch person record from DB; read `thumbnail_path` from `known_persons`. **Do not construct the path from person_id alone** — thumbnail files are named `{person_id}_{embedding_id}.jpg` and the authoritative path is in `known_persons.thumbnail_path`.

Return `FileResponse(person["thumbnail_path"])`. `404` if person not found, `thumbnail_path` is NULL, or file missing on disk.

#### `GET /api/persons/{id}/samples/{emb_id}/thumbnail`

`FileResponse` (JPEG). 404 if not found or file missing.

#### `GET /api/face-crops`

Query params:
- `dismissed` (bool, default `false`)
- `count_only` (bool, default `false`)

Response 200 (normal):
```json
{
  "crops": [
    {
      "id": 10,
      "event_id": 42,
      "image_path": "/api/face-crops/10/image",
      "dismissed": false,
      "created_at": "2026-03-15T14:32:00",
      "event_timestamp": "2026-03-15T14:32:00"
    }
  ]
}
```

Response 200 (`count_only=true`): `{"count": 3}`

When face recognition is disabled: returns `{"crops": []}` or `{"count": 0}` — does not return 503 (avoids breaking the badge).

#### `POST /api/face-crops/{id}/assign`

Body: exactly one of `{"person_id": N}` or `{"name": "Alice"}`. Both/neither → 422.
Response 200: `{"person_id": 1, "embedding_id": 7, "name": "Alice"}`.
Errors: 404/422/503. See rollback table in §3.

#### `POST /api/face-crops/{id}/dismiss`

Response 204. 404 if not found.

#### `GET /api/face-crops/{id}/image`

`FileResponse` (JPEG). 404 if not found or file missing.

---

## 5. File Changes

All paths relative to the repo root:

| File | Change |
|------|--------|
| `doorbell-addon/src/database.py` | New CREATE TABLE schemas; migration procedure; updated `add_person` signature; new CRUD methods |
| `doorbell-addon/src/face_recognition_service.py` | New cache type; revised `identify_faces()`; new `IdentifiedFace.person_id` field; `save_face_crop()` helper |
| `doorbell-addon/src/app.py` | New endpoints; ring handler crop-saving step; 503 guards; URL serialization for paths |
| `doorbell-addon/src/config.py` | `face_crops_path` property; version bump |
| `doorbell-addon/src/utils.py` | Add `face_crops_path` to `ensure_directories()` |
| `doorbell-addon/web/templates/persons.html` | Two-tab UI; disabled banner |
| `doorbell-addon/web/static/js/persons.js` | New file: Persons page JS + global badge polling |
| `doorbell-addon/web/templates/base.html` | `<span id="unrecognised-count">` in nav; `<script src="static/js/persons.js">` globally |
| `doorbell-addon/config.yaml` | Version bump |
| `doorbell-addon/build.yaml` | Version bump |
| `doorbell-addon/requirements.txt` | Version bump comment |

---

## 6. Out of Scope

- Bulk dismiss / bulk assign
- Automatic face clustering
- Event-modal inline naming (deferred)
- Face recognition enable/disable settings (already in v1.0.132)
