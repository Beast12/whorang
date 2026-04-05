# Card hass.states Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the WhoRang Lovelace card to read last-event data from `hass.states` instead of making HTTP calls to the add-on's ingress URL (which always returns 401).

**Architecture:** The add-on pushes last-event data (event_id, description, image_url) as attributes on `sensor.doorbell_last_event` after every ring, and copies the latest image to `/config/www/whorang_latest.jpg` (served publicly at `/local/whorang_latest.jpg`). The card reads `hass.states['sensor.doorbell_last_event']` in `set hass()` — no HTTP, no auth, works everywhere.

**Tech Stack:** Python (shutil, os), FastAPI/existing HA integration pattern, Vanilla JS custom element

---

## Files

| File | Change |
|------|--------|
| `doorbell-addon/src/ha_integration.py` | Add image copy + event attributes to `update_sensors()` |
| `doorbell-addon/web/static/js/whorang-card.js` | Rewrite: remove all HTTP/ingress, read hass.states |
| `README.md` | Fix sensor entity IDs (whorang_* → doorbell_*) |
| `doorbell-addon/DOCS.md` | Fix sensor entity IDs |
| `doorbell-addon/CHANGELOG.md` | Add v1.0.160 entry |
| `doorbell-addon/config.yaml` | Bump version to 1.0.160 |
| `doorbell-addon/build.yaml` | Bump version to 1.0.160 |
| `doorbell-addon/requirements.txt` | Bump version comment to 1.0.160 |
| `doorbell-addon/src/config.py` | Bump app_version to 1.0.160 |

---

## Task 1: Update `ha_integration.py` — push event attributes + copy image

**Files:**
- Modify: `doorbell-addon/src/ha_integration.py`

- [ ] **Step 1: Add `shutil` import and `_copy_latest_image` helper**

In `ha_integration.py`, add at the top:
```python
import os
import shutil
```

Add this private function after the `_ENTITIES` list and before the `HomeAssistantIntegration` class:

```python
_WWW_LATEST_IMAGE = "/config/www/whorang_latest.jpg"


def _copy_latest_image(image_path: str) -> bool:
    """Copy the given image file to /config/www/whorang_latest.jpg.

    Returns True on success, False if the source file does not exist or copy fails.
    """
    if not image_path or not os.path.isfile(image_path):
        return False
    try:
        os.makedirs(os.path.dirname(_WWW_LATEST_IMAGE), exist_ok=True)
        shutil.copy2(image_path, _WWW_LATEST_IMAGE)
        return True
    except Exception as exc:
        logger.warning("Failed to copy latest image to www", src=image_path, error=str(exc))
        return False
```

- [ ] **Step 2: Update `update_sensors()` to include event attributes and copy image**

Replace the existing `update_sensors()` method body with:

```python
    async def update_sensors(self):
        """Update all sensor states."""
        try:
            from .database import db

            last_event = db.get_last_event()
            total_events = db.get_event_count()
            last_event_time = last_event.timestamp.isoformat() if last_event else "unknown"

            person_detected = (
                last_event is not None
                and (datetime.now() - last_event.timestamp).total_seconds()
                < _PERSON_DETECTED_THRESHOLD_SECS
            )

            # Build last-event attributes for the card to consume from hass.states
            if last_event:
                image_ok = _copy_latest_image(last_event.image_path)
                image_url = (
                    f"/local/whorang_latest.jpg?t={last_event.id}" if image_ok else ""
                )
                last_event_attrs = {
                    "friendly_name": "Doorbell Last Event",
                    "icon": "mdi:doorbell-video",
                    "device_class": "timestamp",
                    "event_id": last_event.id,
                    "description": last_event.ai_message or "",
                    "image_url": image_url,
                }
            else:
                last_event_attrs = {
                    "friendly_name": "Doorbell Last Event",
                    "icon": "mdi:doorbell-video",
                    "device_class": "timestamp",
                    "event_id": None,
                    "description": "",
                    "image_url": "",
                }

            await asyncio.gather(
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
                    "binary_sensor.doorbell_person_detected",
                    "on" if person_detected else "off",
                    {"friendly_name": "Doorbell Person Detected", "device_class": "occupancy", "icon": "mdi:motion-sensor"},
                ),
            )
            logger.debug("Sensors updated successfully")

        except Exception as e:
            logger.error("Failed to update sensors", error=str(e))
```

- [ ] **Step 3: Commit**

```bash
git add doorbell-addon/src/ha_integration.py
git commit -m "feat: push last-event attributes and image to HA sensor and /local/"
```

---

## Task 2: Rewrite `whorang-card.js` — read hass.states, no HTTP

**Files:**
- Modify: `doorbell-addon/web/static/js/whorang-card.js`

- [ ] **Step 1: Replace the file entirely**

Write the complete new card:

```js
// whorang-card.js — WhoRang Lovelace custom card
// Displays the last doorbell ring: image, AI description, timestamp.
// Reads data from hass.states['sensor.doorbell_last_event'] — no HTTP calls.
// The add-on pushes event_id, description, image_url as sensor attributes on each ring.
// Served by HA at /local/whorang-card.js (copied by run.sh on startup).

class WhoRangCard extends HTMLElement {
  constructor() {
    super();
    this._lastEventId = undefined; // tracks last rendered event to skip no-op updates
    this._hass = null;
    this._state = 'loading'; // 'loading' | 'no-events' | 'loaded'
    this._eventData = null;  // { description, image_url, timestamp }
  }

  getCardSize() {
    return 5;
  }

  setConfig(config) {
    this.config = config;
  }

  connectedCallback() {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: 'open' });
    }
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card {
          overflow: hidden;
          cursor: pointer;
        }
        .header {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 12px 16px 8px;
          font-weight: 500;
          color: var(--primary-text-color);
        }
        .header ha-icon {
          --mdc-icon-size: 20px;
          color: var(--primary-color, #03a9f4);
        }
        .image-wrapper {
          position: relative;
          width: 100%;
          aspect-ratio: 16 / 9;
          background: var(--secondary-background-color, #1c1c1f);
          overflow: hidden;
        }
        .image-wrapper img {
          width: 100%;
          height: 100%;
          object-fit: cover;
          display: block;
        }
        .placeholder-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 100%;
          height: 100%;
          color: var(--secondary-text-color, #888);
        }
        .placeholder-icon ha-icon {
          --mdc-icon-size: 48px;
        }
        .body {
          padding: 12px 16px;
        }
        .description {
          color: var(--primary-text-color);
          font-size: 14px;
          line-height: 1.4;
          margin-bottom: 4px;
        }
        .timestamp {
          color: var(--secondary-text-color, #888);
          font-size: 12px;
          text-align: right;
        }
        .state-message {
          padding: 24px 16px;
          text-align: center;
          color: var(--secondary-text-color, #888);
          font-size: 14px;
        }
        .spinner {
          display: flex;
          justify-content: center;
          padding: 24px;
        }
      </style>
      <ha-card></ha-card>
    `;

    this.shadowRoot.querySelector('ha-card').addEventListener('click', () => {
      if (!this._hass) return;
      // Navigate to the WhoRang sidebar panel
      const panel = Object.values(this._hass.panels || {}).find(p => {
        const path = p.url_path || '';
        return path === 'whorang' || path.endsWith('_whorang');
      });
      if (panel) {
        this.dispatchEvent(new CustomEvent('hass-navigate', {
          detail: { path: '/' + panel.url_path },
          bubbles: true,
          composed: true,
        }));
      }
    });

    this._render();
  }

  set hass(hass) {
    this._hass = hass;

    const stateObj = hass.states['sensor.doorbell_last_event'];
    if (!stateObj) {
      // Sensor not yet registered — keep spinner
      return;
    }

    const eventId = stateObj.attributes.event_id ?? null;

    // Skip re-render if nothing changed
    if (eventId === this._lastEventId) return;
    this._lastEventId = eventId;

    if (!eventId || stateObj.state === 'unknown') {
      this._state = 'no-events';
      this._eventData = null;
    } else {
      this._state = 'loaded';
      this._eventData = {
        description: stateObj.attributes.description || '',
        image_url: stateObj.attributes.image_url || '',
        timestamp: stateObj.state, // ISO timestamp string
      };
    }

    this._render();
  }

  _escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  _render() {
    const card = this.shadowRoot && this.shadowRoot.querySelector('ha-card');
    if (!card) return;

    if (this._state === 'loading') {
      card.innerHTML = `
        <div class="header"><ha-icon icon="mdi:doorbell"></ha-icon> WhoRang — Last Ring</div>
        <div class="spinner"><ha-circular-progress active></ha-circular-progress></div>
      `;
      return;
    }

    if (this._state === 'no-events') {
      card.innerHTML = `
        <div class="header"><ha-icon icon="mdi:doorbell"></ha-icon> WhoRang — Last Ring</div>
        <div class="state-message">No rings recorded yet</div>
      `;
      return;
    }

    // Loaded state
    const ev = this._eventData;
    const hasImage = !!ev.image_url;
    const description = this._escapeHtml(ev.description || 'No description available');
    const timestamp = this._relativeTime(ev.timestamp);

    const imageHtml = hasImage
      ? `<img src="${this._escapeHtml(ev.image_url)}" alt="Doorbell image"
              onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
      : '';
    const placeholderHtml = `
      <div class="placeholder-icon" style="${hasImage ? 'display:none' : ''}">
        <ha-icon icon="mdi:camera-off"></ha-icon>
      </div>`;

    card.innerHTML = `
      <div class="header"><ha-icon icon="mdi:doorbell"></ha-icon> WhoRang — Last Ring</div>
      <div class="image-wrapper">
        ${imageHtml}
        ${placeholderHtml}
      </div>
      <div class="body">
        <div class="description">${description}</div>
        <div class="timestamp">${timestamp}</div>
      </div>
    `;
  }

  _relativeTime(iso) {
    const now = Date.now();
    const then = new Date(iso).getTime();
    const diffSecs = Math.floor((now - then) / 1000);
    if (diffSecs < 30) return 'just now';
    if (diffSecs < 90) return '1m ago';
    const diffMins = Math.round(diffSecs / 60);
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.round(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${Math.round(diffHours / 24)}d ago`;
  }
}

customElements.define('whorang-card', WhoRangCard);
```

- [ ] **Step 2: Commit**

```bash
git add doorbell-addon/web/static/js/whorang-card.js
git commit -m "feat: rewrite card to read hass.states — no HTTP calls"
```

---

## Task 3: Fix README and DOCS sensor names

**Files:**
- Modify: `README.md`
- Modify: `doorbell-addon/DOCS.md`

- [ ] **Step 1: Fix `README.md` sensor table**

In `README.md`, replace:
```markdown
| Sensor | Description |
|--------|-------------|
| `sensor.whorang_last_event_id` | ID of the most recent event |
| `sensor.whorang_last_event_time` | Timestamp of the most recent event |
| `sensor.whorang_total_events` | Total number of stored events |
```

With:
```markdown
| Sensor | Description |
|--------|-------------|
| `sensor.doorbell_last_event` | Timestamp of the most recent ring (attributes: `event_id`, `description`, `image_url`) |
| `sensor.doorbell_total_events` | Total number of stored rings |
| `binary_sensor.doorbell_person_detected` | On for 30 s after a ring |
```

- [ ] **Step 2: Fix `DOCS.md` sensor list**

In `doorbell-addon/DOCS.md`, replace:
```markdown
- `sensor.whorang_last_event_id`
- `sensor.whorang_last_event_time`
- `sensor.whorang_total_events`
```

With:
```markdown
- `sensor.doorbell_last_event` — timestamp of last ring; attributes: `event_id`, `description`, `image_url`
- `sensor.doorbell_total_events` — total rings recorded
- `binary_sensor.doorbell_person_detected` — on for 30 s after a ring
```

- [ ] **Step 3: Commit**

```bash
git add README.md doorbell-addon/DOCS.md
git commit -m "docs: fix sensor entity IDs to match actual code (doorbell_* not whorang_*)"
```

---

## Task 4: Version bump, CHANGELOG, and release

**Files:**
- Modify: `doorbell-addon/CHANGELOG.md`
- Modify: `doorbell-addon/config.yaml`
- Modify: `doorbell-addon/build.yaml`
- Modify: `doorbell-addon/requirements.txt`
- Modify: `doorbell-addon/src/config.py`

- [ ] **Step 1: Add CHANGELOG entry**

In `doorbell-addon/CHANGELOG.md`, add after the `# Changelog` header block and before `## [1.0.159]`:

```markdown
## [1.0.160] - 2026-04-03

### Fixed
- `whorang-card`: eliminated all HTTP calls to the add-on. The card now reads last-event data directly from `hass.states['sensor.doorbell_last_event']` — works on any network without authentication issues.

### Changed
- `sensor.doorbell_last_event` now includes attributes: `event_id`, `description`, `image_url`. The latest ring image is copied to `/config/www/whorang_latest.jpg` (served at `/local/`) on every ring.
- Lovelace card click navigates to the WhoRang sidebar panel instead of opening a new tab.

```

- [ ] **Step 2: Bump version in all four files**

`doorbell-addon/config.yaml` line 3:
```yaml
version: "1.0.160"
```

`doorbell-addon/build.yaml` lines 9 and 13:
```yaml
  org.opencontainers.image.version: "1.0.160"
...
  DOORBELL_VERSION: "1.0.160"
```

`doorbell-addon/requirements.txt` last line:
```
# Version: 1.0.160
```

`doorbell-addon/src/config.py`:
```python
    app_version: ClassVar[str] = "1.0.160"
```

- [ ] **Step 3: Commit and tag**

```bash
git add doorbell-addon/CHANGELOG.md doorbell-addon/config.yaml doorbell-addon/build.yaml doorbell-addon/requirements.txt doorbell-addon/src/config.py
git commit -m "chore: release v1.0.160 — card reads hass.states, no HTTP"
git tag v1.0.160
git push origin main
git push origin v1.0.160
```
