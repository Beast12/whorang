# WhoRang Lovelace Card — Design Spec

**Date:** 2026-03-23
**Status:** Approved

---

## Overview

A Home Assistant Lovelace custom card that displays the last doorbell ring from the WhoRang addon. The card shows the ring image, AI-generated description, and relative timestamp. It updates automatically when a new ring fires via the HA WebSocket event system, with a 60-second polling fallback.

---

## Scope

- One new static JS file: `doorbell-addon/web/static/js/whorang-card.js`
- Zero backend changes — the addon already serves `/web/static/` and existing API endpoints are sufficient
- Users register the file once as a Lovelace resource, then add the card via YAML

---

## Constraints

- **Local network / HTTP only.** If HA is served over HTTPS, a card fetching `http://...` will be blocked by the browser as mixed content. This card is designed for local-network HTTP deployments. This is a known limitation; HTTPS support is out of scope.
- **Direct port 8099 access.** The card fetches the WhoRang API directly on port 8099, bypassing the HA ingress proxy. This is intentional. The addon already has `allow_origins: ["*"]` CORS headers, so browser cross-origin requests from the HA dashboard succeed.

---

## Architecture

### File location

```
doorbell-addon/web/static/js/whorang-card.js
```

Served at: `http://<whorang-host>:<port>/static/js/whorang-card.js`

The addon already mounts `web/static/` as a static file directory via FastAPI `StaticFiles`, so no backend changes are needed.

### User setup (one-time)

**Step 1 — Register resource**

In HA → Settings → Dashboards → Resources:
- **URL:** `http://<whorang-ip>:8099/static/js/whorang-card.js`
- **Type:** JavaScript module

**Step 2 — Add card to dashboard**

```yaml
type: custom:whorang-card
url: http://<whorang-ip>:8099
```

The resource URL (where HA loads the JS file) and the card `url` config (where the card calls the API at runtime) are **independent values**. Both should point at the same WhoRang host:port, but they serve different purposes and may differ in advanced setups.

The `url` config value is normalised by the card at runtime — a trailing slash is stripped if present, so both `http://host:8099` and `http://host:8099/` are accepted.

---

## Card Behaviour

### Data source

- **Events:** `GET {url}/api/events?limit=1` — returns the single most recent doorbell event
- **Response shape:** `{ events: [{ id, timestamp, image_path, ai_message }] }`
- **Image URL:** `{url}/api/images/{filename}` where `filename = image_path.split('/').pop()`
- **Empty image_path:** if `image_path` is null, empty string, or `split('/').pop()` yields `""`, the image element is hidden and a placeholder icon is shown instead

### Update mechanism

1. **On first `hass` assignment:** call `_fetchLastEvent()` immediately. The `hass` setter is the entry point for the first fetch — `connectedCallback` does not trigger a fetch because `hass` may not be available yet at that point.
2. **WebSocket subscription:** on first `hass` assignment, subscribe to the `doorbell_ring` HA event via `hass.connection.subscribeEvents`. The event payload is **not used directly** — receiving the event triggers a fresh `_fetchLastEvent()` call. This avoids race conditions where the event fires before the database write completes. Because the server-side debounce (10 seconds) prevents back-to-back rings, concurrent fetches from the same card are not a meaningful risk; no client-side fetch-deduplication guard is needed.
3. **Polling:** a single 60-second `setInterval` (started unconditionally from `connectedCallback`) drives both the data refresh (`_fetchLastEvent()`) and the relative-timestamp recalculation (`_updateTimestamp()`). One timer, not two. `_updateTimestamp()` is a no-op when `_eventData` is null.

### Subscription lifecycle

- `_unsubscribeEvent` is **initialised to a no-op function** (`() => {}`) in the constructor so `disconnectedCallback` can always call it safely, even if the card is removed before the first `hass` assignment or if `subscribeEvents` threw.
- The `_subscribed` boolean flag (initialised to `false`) prevents re-subscription when the `hass` setter is called on subsequent HA state updates.
- `_startPolling()` is called from `connectedCallback` (not from `set hass`) so polling starts unconditionally, independent of WebSocket subscription success or failure. `_startPolling` is idempotent — it checks `_pollInterval` and returns immediately if the interval is already running, preventing double-registration if `connectedCallback` fires more than once.
- `disconnectedCallback` always calls `_unsubscribeEvent()` and clears `_pollInterval`.

### States

| State | Display |
|-------|---------|
| Loading | Centered spinner |
| No events | "No rings recorded yet" placeholder text |
| Loaded | Image + AI description + relative timestamp |
| API error | "Unable to reach WhoRang" message, no crash |
| Empty image_path | Placeholder icon instead of `<img>` |

---

## Visual Layout

```
┌─────────────────────────────────┐
│ 🔔 WhoRang — Last Ring          │
├─────────────────────────────────┤
│ ┌─────────────────────────────┐ │
│ │                             │ │
│ │       doorbell image        │ │
│ │      (16:9, full width)     │ │
│ │                             │ │
│ └─────────────────────────────┘ │
│ "A person in a blue jacket was  │
│  at the door"                   │
│                          2m ago │
└─────────────────────────────────┘
```

- **Header:** bell icon + "WhoRang — Last Ring"
- **Image:** full-width, 16:9 aspect ratio, `object-fit: cover`. `onerror` handler hides the element and shows a placeholder icon on load failure.
- **AI description:** `ai_message` field; falls back to "No description available" if empty or null
- **Timestamp:** relative ("just now", "2m ago", "1h ago"), right-aligned, recalculated by the shared 60-second interval
- **Click target:** a click listener is attached to the `ha-card` element itself. No child elements call `stopPropagation`, so any click anywhere on the card opens `{url}/gallery` in a new tab.

### Styling

- Renders as an `ha-card` custom element — picks up HA's built-in card border-radius, box-shadow, and padding
- Uses HA CSS custom properties (`--primary-text-color`, `--secondary-text-color`, `--card-background-color`) so it adapts to light/dark theme automatically
- No external CSS or JS dependencies

---

## Implementation

### Registration

```js
customElements.define('whorang-card', WhoRangCard);
```

Plain `HTMLElement` subclass — no LitElement, no build step, no bundler.

### Config

```js
setConfig(config) {
  if (!config.url) throw new Error('WhoRang URL is required (e.g. http://192.168.10.28:8099)');
  this._baseUrl = config.url.replace(/\/$/, ''); // strip trailing slash
  this.config = config;
}
```

### Key methods

| Method | Purpose |
|--------|---------|
| `setConfig(config)` | Validate `url`, normalise trailing slash, store config |
| `set hass(hass)` | On first call: fetch + subscribe to `doorbell_ring` event. Guarded by `_subscribed` flag. |
| `connectedCallback()` | Set up initial DOM structure; calls `_startPolling()` unconditionally |
| `disconnectedCallback()` | Call `_unsubscribeEvent()`, clear `_pollInterval` |
| `_fetchLastEvent()` | `GET /api/events?limit=1`, update `_eventData`, call `_render()` |
| `_render()` | Full DOM update from current state and `_eventData` |
| `_updateTimestamp()` | Recalculate and update only the timestamp element (no-op if `_eventData` is null) |
| `_relativeTime(iso)` | Convert ISO timestamp to human-readable relative string |
| `_startPolling()` | Idempotent — returns immediately if `_pollInterval` already set. Otherwise starts single `setInterval(60000)` calling both `_fetchLastEvent` and `_updateTimestamp` |
| `getCardSize()` | Returns `5` — a full-width 16:9 image plus header and description text occupies approximately 5 HA grid rows (~250px). This is a layout hint only and does not clip content. |

### Instance properties

| Property | Purpose |
|----------|---------|
| `_baseUrl` | Normalised WhoRang base URL |
| `_subscribed` | Boolean flag preventing duplicate WebSocket subscriptions |
| `_unsubscribeEvent` | Initialised to `() => {}` no-op; replaced by the function returned by `subscribeEvents`. Always safe to call. |
| `_pollInterval` | `setInterval` handle; cleared in `disconnectedCallback` |
| `_eventData` | Last fetched event object or `null` |

---

## Error handling

- API fetch failures are caught; card shows error state, no unhandled rejections
- Missing `url` config throws a descriptive error in `setConfig` so HA shows it in the card editor
- WebSocket subscription failure is caught and silently ignored — polling covers it
- Image `onerror`: hides `<img>`, renders a placeholder camera icon

---

## What is NOT in scope

- Card editor UI (visual config editor in HA dashboard edit mode) — YAML-only configuration
- Multiple recent rings — last ring only
- Face recognition data on the card
- Stats, binary sensor state, or weather data
- HACS packaging
- HTTPS / mixed-content support
