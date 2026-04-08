# WhoRang — Doorbell History for Home Assistant

[![Version](https://img.shields.io/badge/version-1.0.163-blue.svg)](https://github.com/Beast12/whorang/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Home Assistant Add-on](https://img.shields.io/badge/Home%20Assistant-Add--on-blue.svg)](https://www.home-assistant.io/)
[![Build](https://github.com/Beast12/whorang/actions/workflows/build.yml/badge.svg)](https://github.com/Beast12/whorang/actions/workflows/build.yml)

WhoRang is a Home Assistant add-on that captures a doorbell image when your bell rings, stores the event (image + timestamp + weather + optional AI description), and shows everything in a clean web UI. All processing is local — no cloud.

---

## Features

- **Event history** — every ring is stored with image, timestamp, weather snapshot, and an optional comment or AI description
- **Web UI** — dashboard, gallery with date/person filtering, and settings page accessible via HA ingress
- **Face recognition** — optional InsightFace-powered identification of known people (disabled by default)
- **HA sensors** — three sensors updated on each ring for use in automations and dashboards
- **Notifications** — HA push notifications and optional Gotify / generic webhook
- **Weather integration** — captures current conditions from any HA weather entity on each ring
- **AI description** — accepts AI-generated text via the ring endpoint (works with [LLM Vision](https://github.com/valentinfrlch/ha-llmvision))
- **Multi-arch** — amd64 and aarch64 images built and published to GHCR

---

## Installation

1. In Home Assistant go to **Settings → Add-ons → Add-on Store**
2. Click **⋮ → Repositories** and add `https://github.com/Beast12/whorang`
3. Find **WhoRang Doorbell** and click **Install**
4. Start the add-on — it appears as **WhoRang Doorbell** in your sidebar

---

## Configuration

Set these in the add-on **Configuration** tab. You must provide either `camera_entity` or `camera_url`.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `camera_entity` | string | `""` | HA camera entity ID (e.g. `camera.front_door`) — recommended |
| `camera_url` | string | — | Direct RTSP or HTTP URL — fallback if no entity |
| `storage_path` | string | `/share/doorbell` | Where images and the database are stored |
| `retention_days` | int (1–365) | `30` | Events older than this are deleted automatically |
| `notification_webhook` | string | `""` | Gotify or generic webhook URL |
| `ha_access_token` | string | `""` | Long-lived HA token (only needed outside the Supervisor) |
| `face_recognition_enabled` | bool | `false` | Load InsightFace model at startup |
| `face_recognition_model` | string | `buffalo_sc` | `buffalo_sc` (fast) / `buffalo_s` / `buffalo_l` (accurate) |

> All settings can also be changed from the **Settings** page in the web UI without restarting.

---

## Triggering a Ring

The add-on exposes a single endpoint:

```
POST http://<addon-hostname>:8099/api/doorbell/ring
```

The easiest way to set this up: open the add-on web UI → **Settings → Trigger Helper**, select your doorbell binary sensor, and click **Copy automation YAML**. It generates the correct `rest_command` and automation YAML for your installation.

Manually, add this to `configuration.yaml`:

```yaml
rest_command:
  doorbell_ring:
    url: "http://<addon-hostname>:8099/api/doorbell/ring"
    method: POST
```

Then create an automation:

```yaml
alias: Doorbell ring
triggers:
  - trigger: state
    entity_id: binary_sensor.your_doorbell_sensor
    from: "off"
    to: "on"
actions:
  - action: rest_command.doorbell_ring
```

> The addon hostname follows the pattern `<hash>-whorang`. Find it on the add-on info page or use the Trigger Helper which fills it in automatically.

For automations that pass AI descriptions, camera snapshots, or weather data, see the [detailed automation guide](doorbell-addon/AUTOMATION.md).

---

## Home Assistant Integration

### Sensors

Six sensors are registered — five are always created, one only when face recognition is enabled:

| Sensor | Description |
|--------|-------------|
| `sensor.doorbell_last_event` | Timestamp of the most recent ring (attributes: `event_id`, `description`) |
| `sensor.doorbell_total_events` | Total number of stored rings |
| `sensor.doorbell_today_count` | Number of rings recorded today (resets at midnight) |
| `sensor.doorbell_last_weather` | Weather at the time of the last ring (e.g. `"sunny, 18°C"`) |
| `binary_sensor.doorbell_person_detected` | On for 30 s after a ring |
| `sensor.doorbell_last_visitor` | Name of the last recognised visitor — only created when face recognition is enabled |

### Event

A `doorbell_ring` event is fired after each ring:

```json
{
  "event_id": 42,
  "timestamp": "2026-04-01T10:30:00",
  "image_path": "/share/doorbell/images/doorbell_20260401_103000.jpg",
  "ai_message": "Someone suspicious-looking with a package"
}
```

Use this in automations for instant reaction without polling:

```yaml
alias: Notify on doorbell ring
triggers:
  - trigger: event
    event_type: doorbell_ring
actions:
  - action: notify.mobile_app_your_phone
    data:
      message: "{{ trigger.event.data.ai_message }}"
      title: "Doorbell"
```

---

## Web UI

Access via the **WhoRang Doorbell** sidebar panel (HA ingress) or directly at `http://your-ha-ip:8099`.

| Page | What it does |
|------|-------------|
| Dashboard | Recent events, statistics, quick links |
| Gallery | All events with image, description, weather; filter by date or person |
| People | Add/manage known people for face recognition |
| Settings | Camera, AI, notifications, face recognition, trigger helper |

---

## Face Recognition

Optional, powered by [InsightFace](https://github.com/deepinsight/insightface). Disabled by default — adds ~2–5 s to startup and meaningful CPU load.

**To enable:**
1. Set `face_recognition_enabled: true` in the add-on configuration (or via Settings UI)
2. Go to the **People** page and add known people with face photos
3. On each ring the add-on will attempt to match detected faces

**Models:** `buffalo_sc` (fastest, recommended for most installs), `buffalo_s`, `buffalo_l` (most accurate). Models are downloaded once and cached in `<storage_path>/insightface_models/`.

---

## Notifications

### HA Push Notifications

Configure in **Settings → Notifications**. Select any `notify.*` service loaded in HA. Each ring sends the AI description and doorbell image (where supported — mobile app, Telegram, HTML5).

### Gotify

Enter a Gotify URL in **Settings → Webhook URL**:

```
https://gotify.example.com/message?token=YOUR_TOKEN
```

The add-on auto-detects Gotify URLs and formats payloads accordingly. Use **Test Notifications** to verify.

### Generic Webhook

Any URL in the webhook field receives a POST with this JSON body on each ring:

```json
{
  "event_id": 42,
  "timestamp": "2026-04-01T10:30:00",
  "ai_message": "Someone at the door",
  "image_path": "/share/doorbell/images/doorbell_20260401_103000.jpg"
}
```

---

## Storage Layout

```
/share/doorbell/
├── database/doorbell.db          SQLite event database
├── images/                       Doorbell snapshots
├── persons/                      Known person thumbnails
├── face_crops/                   Unrecognised face crops (inbox)
├── insightface_models/           InsightFace model cache (downloaded once)
└── config/settings.json          Persisted UI settings
```

---

## Troubleshooting

**No events appearing**
- Check HA logs for REST command errors
- Use the Trigger Helper to verify the addon hostname in your `rest_command` URL
- Check automation traces to confirm the trigger fires

**Camera not capturing**
- Use **Settings → Test Capture** to verify camera connectivity
- For RTSP: test the URL with VLC first
- For HA camera entities: confirm the entity is available in Developer Tools

**Face recognition not matching**
- Upload 3–5 clear, well-lit photos per person from different angles
- Lower the confidence threshold in Settings (lower = more lenient)
- Check add-on logs for InsightFace errors


---

## Development

```bash
git clone https://github.com/Beast12/whorang.git
cd whorang/doorbell-addon
docker build -t whorang .
```

```bash
# Lint (errors only)
flake8 doorbell-addon/src/ --count --select=E9,F63,F7,F82 --show-source --statistics

# Type check
mypy doorbell-addon/src/ --config-file doorbell-addon/mypy.ini

# Tests
python3 -m pytest doorbell-addon/tests/
```

See [TESTING.md](doorbell-addon/TESTING.md) for local install instructions.

---

## Documentation

- [Automation Examples](doorbell-addon/AUTOMATION.md)
- [DOCS.md](doorbell-addon/DOCS.md) — full configuration reference
- [Changelog](doorbell-addon/CHANGELOG.md)
- [Testing Guide](doorbell-addon/TESTING.md)

---

## Support

- Bug reports: [GitHub Issues](https://github.com/Beast12/whorang/issues)
- Discussions: [GitHub Discussions](https://github.com/Beast12/whorang/discussions)

---

## Support the Project

<div align="center">

<a href="https://www.buymeacoffee.com/koen1203" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;">
</a>

<img src="bmc_qr.png" alt="Buy Me A Coffee QR Code" width="150" height="150">

</div>

---

**Made with ❤️ for the Home Assistant community**
