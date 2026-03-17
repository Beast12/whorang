# WhoRang: Automation Integration Design

**Date:** 2026-03-17
**Status:** Approved

## Goal

Move all doorbell ring logic — AI description, push notifications, public image mirroring — out of the HA automation and into the addon. The HA automation is reduced to a single trigger → REST call with no logic. Users who don't want a full automation can call `POST /api/doorbell/ring` any other way they choose.

## Non-Goals

- Detecting the doorbell ring inside the addon (no polling, no WebSocket watcher)
- Supporting LLM providers other than llmvision
- Replacing the existing webhook/Gotify notification path

## Architecture

### Trigger (unchanged)

A minimal HA automation calls `POST /api/doorbell/ring` when the sensor fires. The Settings page generates a ready-to-paste YAML snippet pre-filled with the user's configured trigger entity. The addon's REST endpoint already exists and continues to work for any caller.

### New module: `src/ring_pipeline.py`

A single `run_ring_pipeline(image_path: Optional[str] = None) -> dict` async function that owns the complete ring flow:

1. **Capture** — copy `image_path` if provided and file exists, otherwise call `ha_camera_manager.capture_image()`
2. **Write public copy** — if `public_image_path` is configured, write a timestamped copy to that directory (required before LLM call so HA can read the file)
3. **Parallel analysis** — `asyncio.gather`: llmvision call, face analysis, weather fetch — all non-blocking, all failures silently degrade
4. **Save event** — persist to SQLite via `db.add_doorbell_event()`
5. **Save face crops** — unrecognised faces saved to `face_crops_path`
6. **Send HA notifications** — call each configured `notify.*` service with a payload tailored to service type
7. **Fire HA event + update sensors** — `ha_integration.handle_doorbell_ring()`

Returns `{"event_id": ..., "ai_message": ..., "ai_title": ...}`.

### Modified: `app.py` ring handler

The `POST /api/doorbell/ring` handler is reduced to:
- Parse `ai_message` and `image_path` form fields
- If `ai_message` is provided (caller already has it), pass it to `run_ring_pipeline()` to skip the LLM call
- Call `run_ring_pipeline()`, return result

### New API endpoints

- `GET /api/settings/notify-services` — fetches `notify.*` services from HA supervisor API, returns list with `name`, `image_capable` flag
- `GET /api/settings/binary-sensors` — fetches `binary_sensor.*` entities from HA, returns list of `{entity_id, friendly_name}`

## New Settings Fields

Added to `config.py` and persisted to `settings.json`:

### AI Description

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `llmvision_enabled` | `bool` | `False` | Enable AI-generated description |
| `llmvision_provider` | `Optional[str]` | `None` | llmvision provider ID |
| `llmvision_model` | `str` | `"gpt-4o-mini"` | LLM model name |
| `llmvision_prompt` | `str` | see below | Prompt sent with image |
| `llmvision_max_tokens` | `int` | `100` | Max tokens in response |
| `default_message` | `str` | `"Someone is at the door"` | Used when LLM is off or fails |

Default prompt:
> "You are my sarcastic funny security guard. Describe what you see in one funny one-liner of max 10 words. Only describe the person, vehicle or animal."

### Notifications

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ha_notify_services` | `list[str]` | `[]` | Selected HA notify service names |

### Public Image

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `public_image_path` | `Optional[str]` | `None` | Directory to write public copies, e.g. `/config/www` |

### Trigger Helper (display only)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `trigger_entity` | `Optional[str]` | `None` | Binary sensor entity ID — used only to generate the automation YAML snippet |

## LLM Integration

The addon calls `llmvision.image_analyzer` via the HA supervisor API:

```
POST http://supervisor/core/api/services/llmvision/image_analyzer?return_response=true
Authorization: Bearer <supervisor_token>

{
  "provider": "<llmvision_provider>",
  "model": "<llmvision_model>",
  "message": "<llmvision_prompt>",
  "image_file": "<public_image_path>/doorbell_<timestamp>.jpg",
  "max_tokens": <llmvision_max_tokens>,
  "temperature": 0.2,
  "generate_title": true
}
```

Response: `{"response": {"response_text": "...", "title": "..."}}`.

**Ordering:** public image copy is written before the parallel analysis step so the file exists when HA reads it.

**Degradation rules:**
- `llmvision_enabled = False` → use `default_message`, skip LLM call entirely
- `public_image_path` not set → skip LLM call, use `default_message`
- LLM call fails (integration not installed, API error, timeout) → log warning, use `default_message`
- LLM never blocks the ring event from being saved or notifications from being sent

**Caller-provided message:** if the ring request arrives with `ai_message` already set (legacy automation still sends it), the LLM call is skipped and the provided message is used directly.

## Notification System

### Service discovery

`GET /api/services` from supervisor returns all HA services. The addon filters for the `notify` domain and classifies each:

| Pattern | Classification | Payload |
|---------|---------------|---------|
| `mobile_app_*` | Image-capable | title + message + `data.image` + priority |
| `telegram_*`, `html5_*` | Image-capable | title + message + `data.image` |
| `tts_*`, `alexa_media_*`, `google_*` | Audio-only | message only |
| Everything else | Unknown | Full payload (data block may be ignored by HA) |

### Rich payload (image-capable)

```json
{
  "title": "<ai_title or 'Doorbell'>",
  "message": "<ai_message or default_message>",
  "data": {
    "image": "/local/<filename>",
    "ttl": 0,
    "priority": "high"
  }
}
```

The `image` URL uses `/local/<filename>` — the HA convention for files in `/config/www/`. Requires `public_image_path` to be set. If unset, the `data.image` field is omitted.

### Audio-only payload

```json
{ "message": "<ai_message or default_message>" }
```

### Existing webhook/Gotify

Kept unchanged and runs in parallel with HA notify calls.

## Settings UI

### AI Description card (new — below Weather)

- Enable/disable toggle
- Provider ID text field with hint
- Model text field
- Prompt textarea (pre-filled with default)
- Default message text field
- Max tokens slider (50–200)
- Save button

### Notifications card (replaces current webhook-only card)

Two sub-sections:
- **HA Push** — checklist of all `notify.*` services loaded from HA. Each entry shows service name and a type badge (📱 Mobile / 🔊 Audio / 📡 Other). Refresh button. Multi-select.
- **Webhook / Gotify** — existing webhook URL field, unchanged.

Single Save button.

### Public Image card (new — within Storage section)

- Path text field, e.g. `/config/www`
- Helper text: "Required for AI description. Images written here are served by HA at `/local/<filename>`."
- Save button

### Trigger Helper card (new — within Home Assistant section)

- Binary sensor entity dropdown (loaded from HA, filtered to `binary_sensor.*`)
- "Copy automation YAML" button — copies ready-to-paste minimal automation to clipboard
- The generated YAML:

```yaml
alias: Doorbell ring
triggers:
  - trigger: state
    entity_id: <trigger_entity>
    from: "off"
    to: "on"
actions:
  - action: rest_command.doorbell_ring
```

## Files Changed

| File | Change |
|------|--------|
| `src/ring_pipeline.py` | New — full ring pipeline |
| `src/app.py` | Ring handler becomes thin wrapper; two new settings API endpoints |
| `src/config.py` | New settings fields + persisted fields list updated |
| `src/utils.py` | New `call_llmvision()` and `send_ha_notification()` helpers in `HomeAssistantAPI` |
| `web/templates/settings.html` | Four new/revised settings cards |
| `web/static/js/settings.js` | New JS for notify service checklist, binary sensor dropdown, YAML copy |
| `doorbell-addon/config.yaml` | `config:ro` → `config:rw` |

## Backward Compatibility

- `POST /api/doorbell/ring` continues to accept `ai_message` and `image_path` form fields exactly as today
- If `ai_message` is provided by the caller, the LLM step is skipped
- Existing webhook/Gotify notifications are unaffected
- Users with no settings configured get identical behaviour to the current addon

## Testing

Each new unit is tested independently:
- `ring_pipeline.py` — mock all external calls, verify stage ordering and degradation
- `call_llmvision()` — mock supervisor HTTP, verify payload shape and response parsing
- `send_ha_notification()` — verify image-capable vs audio-only payload selection
- Settings API endpoints — verify HA service list filtering and classification
- Settings page JS — manual smoke test for checklist population, YAML copy
