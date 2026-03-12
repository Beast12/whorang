# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WhoRang is a **Home Assistant add-on** for doorbell event history. It captures an image when the doorbell rings, records the event (image + timestamp + weather + optional comment), and exposes a web UI and REST API. It runs as a Docker container on port 8099. All processing is local — no cloud dependencies.

## Development Commands

All source code lives in `doorbell-addon/`. Most commands should be run from that directory.

### Code Quality (mirrors CI/CD checks)

```bash
# Lint (errors only)
flake8 doorbell-addon/src/ --count --select=E9,F63,F7,F82 --show-source --statistics

# Lint (style warnings, non-blocking)
flake8 doorbell-addon/src/ --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

# Format check
black --check doorbell-addon/src/

# Auto-format
black doorbell-addon/src/

# Import sort check
isort --check-only --profile black doorbell-addon/src/

# Type check
mypy doorbell-addon/src/ --config-file doorbell-addon/mypy.ini
```

### Build

```bash
# Build Docker image locally
cd doorbell-addon && docker build -t doorbell-face-recognition .
```

### Local Installation for Testing

```bash
cd doorbell-addon && sudo ./install-local.sh
```

## Architecture

### Service Modules (`doorbell-addon/src/`)

| Module | Responsibility |
|--------|---------------|
| `app.py` | FastAPI app, all REST endpoints, middleware |
| `config.py` | Pydantic BaseSettings — reads from env vars set by `run.sh` |
| `database.py` | SQLite; `doorbell_events` table (id, timestamp, image_path, ai_message, weather_*) |
| `ha_camera.py` | Camera image capture — HA camera proxy, direct HTTP URL, or RTSP via ffmpeg |
| `ha_integration.py` | Registers HA sensors and fires `doorbell_ring` events |
| `utils.py` | `HomeAssistantAPI` async HTTP client, `NotificationManager` (HA, Gotify, webhooks) |

### Request Flow

1. HA automation calls `POST /api/doorbell/ring`
2. `app.py` captures an image via `ha_camera.py` (`capture_image`)
3. Weather data fetched from HA if `weather_entity` is configured
4. Event persisted to SQLite via `database.py`
5. `ha_integration.py` updates HA sensors and fires `doorbell_ring` event
6. `utils.py` sends webhook/Gotify notifications

### Web UI

Jinja2 templates in `doorbell-addon/web/templates/` with static assets in `doorbell-addon/web/static/`. Pages: dashboard (recent events table), gallery (event grid with date filter), settings.

### Comment Field

The `ai_message` column in `doorbell_events` stores the comment/note for an event. It can be set at ring time (passed as `ai_message` form field to `POST /api/doorbell/ring`) or updated later via `POST /api/events/{id}/comment`.

### Configuration

The add-on reads its config from `/data/options.json` (Home Assistant supervisor convention). `run.sh` translates this to environment variables that Pydantic `Settings` in `config.py` consumes.

Key settings: `camera_entity`, `camera_url`, `storage_path`, `retention_days`, `notification_webhook`, `weather_entity`, `ha_access_token`.

## Versioning

Releases are triggered by git tags (`v*.*.*`). Version must be consistent across three files — the CI will fail otherwise:
- `doorbell-addon/config.yaml` (the `version:` field)
- `doorbell-addon/build.yaml` (the `org.opencontainers.image.version:` label)
- `doorbell-addon/requirements.txt` (comment `# Version: X.Y.Z`)

## Key Constraints

- **Multi-arch builds** (amd64, aarch64) use the `home-assistant/builder` action and separate `build_from` base images in `build.yaml`.
- The `IngressAuthMiddleware` in `app.py` handles Home Assistant ingress token authentication and CORS — changes here can break HA integration.
- RTSP capture uses `ffmpeg` (system package); HTTP/HTTPS URLs use `requests.get`; HA camera entities use `/api/camera_proxy/{entity_id}`.
