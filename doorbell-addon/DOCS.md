# WhoRang Doorbell — Documentation

WhoRang captures a snapshot when your doorbell rings, stores the event with weather data and an optional AI-generated description, and shows everything in a clean web UI accessible via Home Assistant ingress.

## Quick Start

1. Install the add-on and start it.
2. Open the web UI via the **WhoRang Doorbell** panel in your HA sidebar.
3. Go to **Settings** and configure your camera.
4. Create a minimal HA automation to call the ring endpoint when your doorbell sensor fires (see below).

---

## Triggering a Ring

The add-on exposes a single REST endpoint:

```
POST http://<addon-hostname>:8099/api/doorbell/ring
```

The simplest way to call it is with a `rest_command`. Add this to `configuration.yaml`:

```yaml
rest_command:
  doorbell_ring:
    url: "http://<addon-hostname>:8099/api/doorbell/ring"
    method: POST
```

> The addon hostname follows the pattern `<hash>-whorang`. Find it on the add-on info page, or use the **Trigger Helper** in the web UI Settings which fills it in automatically.

Then create a minimal automation:

```yaml
alias: Doorbell ring
triggers:
  - trigger: state
    entity_id: binary_sensor.YOUR_DOORBELL_SENSOR
    from: "off"
    to: "on"
actions:
  - action: rest_command.doorbell_ring
```

The **Trigger Helper** card in Settings can generate this YAML for you — select your binary sensor and click **Copy automation YAML**.

### Reduce capture latency (recommended)

By default WhoRang captures the camera frame when it *receives* the ring, which can be ~0.5–2s after the button press — enough for a moving visitor to turn away or change angle. To capture at the exact moment of the press instead, snapshot your camera in the automation and hand the file to WhoRang via the `image_path` field. WhoRang then uses that frame and skips its own (later) capture.

If you have a **camera entity** configured (Settings → Camera), the **Trigger Helper** generates this lower-latency version automatically:

```yaml
rest_command:
  doorbell_ring:
    url: "http://<addon-hostname>:8099/api/doorbell/ring"
    method: POST
    content_type: "application/x-www-form-urlencoded"
    payload: "image_path={{ image_path | default('') }}"

alias: Doorbell ring
triggers:
  - trigger: state
    entity_id: binary_sensor.YOUR_DOORBELL_SENSOR
    from: "off"
    to: "on"
variables:
  snapshot_path: "/config/www/whorang_last_press.jpg"
actions:
  - action: camera.snapshot
    target:
      entity_id: camera.YOUR_DOORBELL_CAMERA
    data:
      filename: "{{ snapshot_path }}"
  - action: rest_command.doorbell_ring
    data:
      image_path: "{{ snapshot_path }}"
```

The `default('')` keeps the `rest_command` backward compatible — callers that don't pass `image_path` fall back to WhoRang's own capture. Confirm it's working in the add-on log: a ring shows `Using pre-captured snapshot …` instead of `Image captured from HA camera entity`.

---

## Settings

All settings are managed through the **Settings** page in the web UI. Changes are saved to `settings.json` and persist across restarts.

### Camera

| Setting | Description |
|---------|-------------|
| Camera Entity | HA camera entity (`camera.front_door`) — recommended |
| Camera URL | Direct RTSP or HTTP URL — fallback if no entity |

### AI Description (requires llmvision integration)

| Setting | Default | Description |
|---------|---------|-------------|
| Enable AI description | off | Call llmvision to describe who's at the door |
| Provider ID | — | Your llmvision provider (e.g. `openai`) |
| Model | `gpt-4o-mini` | LLM model to use |
| Prompt | sarcastic one-liner | Sent with the image to the LLM |
| Max tokens | 100 | Maximum response length |
| Default message | `Someone is at the door` | Used when AI is disabled or fails |

> **Note:** AI description requires **Public Image Path** to be set, and the [llmvision](https://github.com/valentinfrlch/ha-llmvision) Home Assistant integration to be installed.

### Notifications

**HA Push** — select any `notify.*` services loaded from HA. Each ring sends a push notification with the AI description and a doorbell image. Mobile app, Telegram, and HTML5 services receive the image; TTS/Alexa/Google services receive the message only.

**Webhook / Gotify** — optional webhook URL. Supports Gotify (`/message?token=...`) and generic POST webhooks.

### Public Image

Directory where the add-on writes a timestamped copy of each doorbell snapshot (e.g. `/config/www`). Files written here are served by HA at `/local/<filename>` and are required for:
- AI description (llmvision reads the file directly)
- Image attachments in push notifications

### Storage

| Setting | Default | Description |
|---------|---------|-------------|
| Storage Path | `/share/doorbell` | Where events, images, and the database are stored |
| Retention Days | 30 | Events older than this are automatically deleted |

### Face Recognition (optional)

Powered by [InsightFace](https://github.com/deepinsight/insightface). Disabled by default — enabling it adds ~2–5 s to startup and meaningful CPU load. Not recommended for Raspberry Pi unless needed.

| Setting | Default | Description |
|---------|---------|-------------|
| Enable | off | Load the InsightFace model at startup |
| Model | `buffalo_sc` | `buffalo_sc` (fast), `buffalo_s` (balanced), `buffalo_l` (accurate) |
| Threshold | 0.45 | Cosine similarity threshold for identity matching |

Manage known persons via the **Persons** page: upload a photo, give the person a name, and the add-on will recognise them on future rings. Unrecognised faces appear in the **Unrecognised** tab where you can promote them to known persons.

### Home Assistant

| Setting | Description |
|---------|-------------|
| HA Access Token | Long-lived token — only needed when running outside the supervisor |

### Trigger Helper

Select your doorbell binary sensor and click **Copy automation YAML** to get a ready-to-paste HA automation including both the `rest_command` definition and the automation trigger.

---

## Home Assistant Integration

The add-on registers sensors and fires events automatically on each ring.

### Sensors

- `sensor.doorbell_last_event` — timestamp of last ring; attributes: `event_id`, `description`
- `sensor.doorbell_total_events` — total rings recorded
- `sensor.doorbell_today_count` — rings recorded today (resets at midnight)
- `sensor.doorbell_last_weather` — weather at the time of the last ring (e.g. `"sunny, 18°C"`)
- `binary_sensor.doorbell_person_detected` — on for 30 s after a ring
- `sensor.doorbell_last_visitor` — name of the last recognised visitor; only created when face recognition is enabled

### Event fired

`doorbell_ring` — fired after every ring with:

```json
{
  "event_id": 42,
  "timestamp": "2026-03-18T10:30:00",
  "image_path": "/share/doorbell/images/doorbell_20260318_103000.jpg",
  "ai_message": "A suspicious-looking package delivery person"
}
```

---

## Storage Layout

```
/share/doorbell/
├── database/doorbell.db       SQLite event database
├── images/                    Doorbell snapshots
├── persons/                   Known person thumbnails
├── face_crops/                Unrecognised face crops (inbox)
├── insightface_models/        InsightFace model cache (downloaded once)
└── config/settings.json       Persisted settings
```

---

## Configuration Options (config.yaml)

These are the initial defaults. All settings can be changed from the web UI after first start.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `camera_entity` | string | `""` | HA camera entity ID |
| `camera_url` | string | — | RTSP or HTTP camera URL |
| `storage_path` | string | `/share/doorbell` | Storage location |
| `retention_days` | int (1–365) | `30` | Event retention period |
| `notification_webhook` | string | `""` | Gotify / webhook URL |
| `ha_access_token` | string | `""` | HA long-lived access token |
| `face_recognition_enabled` | bool | `false` | Enable InsightFace |
| `face_recognition_model` | string | `buffalo_sc` | InsightFace model |

---

## Support

- **Issues**: https://github.com/Beast12/whorang/issues
- **Repository**: https://github.com/Beast12/whorang
