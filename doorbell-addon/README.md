# WhoRang Doorbell

Doorbell event history for Home Assistant. Captures an image when your doorbell rings, records the event with timestamp, weather data, and an optional AI-generated description, and shows everything in a clean web UI accessible via the HA sidebar.

## Features

- **Doorbell event log** — every ring stored with snapshot, timestamp, and weather conditions
- **AI description** — optional one-liner from the [llmvision](https://github.com/valentinfrlch/ha-llmvision) integration (OpenAI, Gemini, etc.)
- **HA push notifications** — send the snapshot and description to any `notify.*` service (mobile app, Telegram, etc.)
- **Optional face recognition** — powered by [InsightFace](https://github.com/deepinsight/insightface); identify known visitors with bounding-box overlays in the UI
- **Dashboard & gallery** — recent events table, image gallery with date filter, face overlay on every photo
- **Privacy-first** — all processing local, no cloud dependencies

## Quick Start

1. Start the add-on.
2. Open the **WhoRang Doorbell** panel in the HA sidebar.
3. Go to **Settings** and configure your camera.
4. Create a simple automation (see below) to call the ring endpoint when your doorbell sensor fires.

## Triggering a Ring

Add a `rest_command` to `configuration.yaml`:

```yaml
rest_command:
  doorbell_ring:
    url: "http://localhost:8099/api/doorbell/ring"
    method: POST
```

Then create an automation:

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

## Configuration Options

All settings are managed through the Settings page in the web UI. The add-on options in `config.yaml` set the initial defaults only.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `camera_entity` | string | `""` | HA camera entity ID (e.g. `camera.front_door`) |
| `camera_url` | string | — | RTSP or HTTP camera URL |
| `storage_path` | string | `/share/doorbell` | Where events, images, and the database are stored |
| `retention_days` | int | `30` | Events older than this are automatically deleted |
| `notification_webhook` | string | `""` | Gotify or generic webhook URL |
| `ha_access_token` | string | `""` | Long-lived HA token (only needed outside supervisor) |
| `face_recognition_enabled` | bool | `false` | Enable InsightFace (adds ~2–5 s startup, CPU load) |
| `face_recognition_model` | string | `buffalo_sc` | `buffalo_sc` (fast), `buffalo_s`, `buffalo_l` (accurate) |

## Home Assistant Integration

### Sensors

- `sensor.whorang_last_event_id`
- `sensor.whorang_last_event_time`
- `sensor.whorang_total_events`

### Event fired on each ring

`doorbell_ring` with payload:

```json
{
  "event_id": 42,
  "timestamp": "2026-03-18T10:30:00",
  "image_path": "/share/doorbell/images/doorbell_20260318_103000.jpg",
  "ai_message": "A suspicious-looking package delivery person"
}
```

## Support

- **Issues**: https://github.com/Beast12/whorang/issues
- **Repository**: https://github.com/Beast12/whorang
