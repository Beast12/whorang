# Face / Person Management — Design Spec

**Date:** 2026-03-16
**Status:** Approved

---

## Overview

WhoRang can detect and identify faces at the doorbell. This feature makes it easy to:

- Name an unrecognised face from the Persons page (inbox flow)
- Add multiple photo samples per person to improve recognition accuracy
- Rename and delete persons
- Dismiss unrecognised faces without naming them

Recognition happens entirely locally; no cloud services are involved.

---

## 1. Data Model

### `known_persons` table (existing, modified)

Remove the `embedding BLOB` column. It becomes a lightweight identity record.

```sql
CREATE TABLE IF NOT EXISTS known_persons (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    thumbnail_path TEXT,          -- avatar: first sample's crop
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### `person_embeddings` table (new)

One row per face sample. A person can have many.

```sql
CREATE TABLE IF NOT EXISTS person_embeddings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id    INTEGER NOT NULL REFERENCES known_persons(id) ON DELETE CASCADE,
    embedding    BLOB NOT NULL,   -- numpy.save bytes
    thumbnail_path TEXT,          -- 200×200 crop for this sample
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### `face_crops` table (new)

Stores unrecognised face crops from ring events so they can be reviewed and assigned later.

```sql
CREATE TABLE IF NOT EXISTS face_crops (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     INTEGER NOT NULL REFERENCES doorbell_events(id) ON DELETE CASCADE,
    image_path   TEXT NOT NULL,   -- /data/persons/crops/{event_id}_{idx}.jpg
    dismissed    BOOLEAN NOT NULL DEFAULT 0,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### Migration

- On startup, `_init_database()` runs `CREATE TABLE IF NOT EXISTS` for both new tables.
- Existing `known_persons` rows: migrate each embedding to a new `person_embeddings` row; drop the `embedding` column via a rename-copy-drop migration.

---

## 2. UI

### Persons page (`/persons`)

Two tabs:

**Known tab**

- 3-column card grid. Each card shows:
  - Avatar circle (first sample's thumbnail)
  - Person name with inline ✏ rename (click pencil → input replaces text, blur/Enter saves)
  - Sample count ("N samples")
  - Thumbnail strip: one 34×34 tile per sample, each with ✕ overlay to delete that sample
  - `+` dashed tile at end of strip → opens file picker to add another sample
  - 🗑 delete button (top-right of card) removes the whole person
  - Warning hint when only 1 sample: "⚠ More samples improve accuracy"
- "Add new person" card (dashed border) at end of grid → opens name input + file picker

**Unrecognised tab**

- 4-column grid of face crop thumbnails with event date/time beneath each
- Clicking a crop selects it (sky-blue border highlight)
- Action panel below grid (visible when a crop is selected):
  - "Existing:" label + one pill-button per known person (avatar + name)
  - Divider
  - "New name…" text input + "Create" button
  - "Dismiss" button (right-aligned)
- Badge in tab header showing count of unreviewed crops (orange)
- Header badge in nav: "● N unrecognised" when count > 0

---

## 3. Recognition Logic

**Multi-embedding matching**

The in-memory embeddings cache changes from `{person_id: np.ndarray}` to `{embedding_id: (person_id, np.ndarray)}`. During `identify_faces()`, all embeddings are compared; the result is attributed to the person with the highest-scoring embedding.

**Saving unrecognised crops**

When `identify_faces()` produces a face with `name == "Unknown"`:

1. Crop the face region (with padding) from the ring image.
2. Save to `/data/persons/crops/{event_id}_{face_idx}.jpg`.
3. Insert a row into `face_crops` with `dismissed=false`.

This happens inside the ring handler in `app.py`, after face identification.

**Assigning a crop to a person**

`POST /api/face-crops/{id}/assign` with body `{person_id: N}` or `{name: "Alice"}`:

1. Load the crop image from disk.
2. Run `analyze_image()` → get embedding.
3. Insert into `person_embeddings` (links to the target person).
4. If this is the person's first sample, save crop as their thumbnail.
5. Mark the `face_crops` row `dismissed=true`.
6. Call `refresh_embeddings_cache()`.

If `name` is given instead of `person_id`, first create the person in `known_persons`, then follow steps 2–6.

**Adding a sample via the Known tab**

`POST /api/persons/{id}/samples` (multipart: image file):

1. Run `analyze_image()` on the uploaded image.
2. Pick face with highest `det_score`.
3. Crop + save thumbnail to `/data/persons/{person_id}_{emb_id}.jpg`.
4. Insert into `person_embeddings`.
5. Refresh cache.

**Removing a sample**

`DELETE /api/persons/{id}/samples/{emb_id}`:

1. Delete `person_embeddings` row.
2. Delete thumbnail file.
3. If the deleted sample was the person's avatar and other samples exist, update `known_persons.thumbnail_path` to the next sample.
4. Refresh cache.

**Dismiss without naming**

`POST /api/face-crops/{id}/dismiss`: sets `dismissed=true`. Crop is hidden from inbox; no embedding stored.

---

## 4. API

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/persons` | List persons (`id`, `name`, `thumbnail_path`, `sample_count`) |
| `POST` | `/api/persons` | Create person — multipart `name` + `image` |
| `DELETE` | `/api/persons/{id}` | Delete person + all embeddings + thumbnail files |
| `PATCH` | `/api/persons/{id}` | Rename — body `{name: "..."}` |
| `POST` | `/api/persons/{id}/samples` | Add sample — multipart `image` |
| `DELETE` | `/api/persons/{id}/samples/{emb_id}` | Remove one sample |
| `GET` | `/api/persons/{id}/thumbnail` | Serve avatar image (FileResponse) |
| `GET` | `/api/face-crops` | List unrecognised crops (`dismissed=false`) |
| `POST` | `/api/face-crops/{id}/assign` | Assign to person — body `{person_id}` or `{name}` |
| `POST` | `/api/face-crops/{id}/dismiss` | Dismiss crop |
| `GET` | `/api/face-crops/{id}/image` | Serve crop image (FileResponse) |

Existing endpoints (`/api/events/{id}/faces`, `/api/face-recognition/status`, etc.) are unchanged.

---

## 5. File Changes Summary

| File | Change |
|------|--------|
| `src/database.py` | Add `person_embeddings` + `face_crops` tables; migrate existing embedding; add CRUD methods for both |
| `src/face_recognition_service.py` | Multi-embedding cache; `add_sample()`, `remove_sample()` methods; save unrecognised crops |
| `src/app.py` | New API endpoints (persons, samples, face-crops); ring handler saves unrecognised crops |
| `web/templates/persons.html` | Two-tab UI (Known + Unrecognised) |
| `web/static/js/persons.js` | Tab switching, inline rename, sample strip, assign panel JS |
| `web/templates/base.html` | Nav badge for unrecognised count |
| `doorbell-addon/config.yaml` | Version bump |
| `doorbell-addon/build.yaml` | Version bump |
| `doorbell-addon/requirements.txt` | Version bump comment |
| `src/config.py` | Version bump (`app_version`) |

---

## 6. Out of Scope

- Bulk dismiss / bulk assign
- Automatic clustering of unrecognised faces
- Event-modal inline naming (Approach A from brainstorming — deferred)
- Face recognition enable/disable settings (already implemented in v1.0.132)
