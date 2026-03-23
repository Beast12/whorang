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

## Architecture

### File location

```
doorbell-addon/web/static/js/whorang-card.js
```

Served at: `http://<whorang-host>:<port>/static/js/whorang-card.js`

The addon already mounts `web/static/` as a static file directory, so no backend changes are needed.

### User setup (one-time)

1. In HA → Settings → Dashboards → Resources, add:
   - **URL:** `http://192.168.10.28:8099/static/js/whorang-card.js`
   - **Type:** JavaScript module

2. Add card to any dashboard:

```yaml
type: custom:whorang-card
url: http://192.168.10.28:8099
```

---

## Card Behaviour

### Data source

- `GET {url}/api/events?limit=1` — fetches the single most recent doorbell event
- Response shape already in use: `{ events: [{ id, timestamp, image_path, ai_message }] }`
- Image served at: `{url}/api/images/{filename}` (existing endpoint)

### Update mechanism

1. **On load:** fetch last event immediately and render
2. **WebSocket subscription:** subscribe to `doorbell_ring` HA event via `hass.connection.subscribeEvents`. On event fire, re-fetch and re-render
3. **Polling fallback:** every 60 seconds, re-fetch regardless — guards against missed WebSocket events

### States

| State | Display |
|-------|---------|
| Loading | Subtle spinner centred in card |
| No events | "No rings recorded yet" placeholder text |
| Loaded | Image + description + timestamp |
| API error | "Unable to reach WhoRang" message, no crash |

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

- **Header:** bell icon (`mdi:doorbell`) + "WhoRang — Last Ring"
- **Image:** full-width, 16:9 aspect ratio, `object-fit: cover`
- **AI description:** `ai_message` field, shown below image; fallback to "No description available" if empty
- **Timestamp:** relative ("just now", "2m ago", "1h ago"), right-aligned, recalculated every 60 seconds
- **Click target:** clicking anywhere on the card opens the WhoRang gallery (`{url}/gallery`) in a new tab

### Styling

- Matches HA dashboard card style: `ha-card` element with `border-radius`, `box-shadow`, `overflow: hidden`
- Uses HA CSS custom properties (`--primary-text-color`, `--secondary-text-color`, `--card-background-color`) so it adapts to light/dark theme automatically
- No external CSS dependencies

---

## Implementation

### Card registration

```js
customElements.define('whorang-card', WhoRangCard);
```

Standard `HTMLElement` subclass — no LitElement dependency, no build step.

### Config

```js
setConfig(config) {
  if (!config.url) throw new Error('WhoRang URL is required');
  this.config = config;
}
```

### hass setter

Called by HA when `hass` object is available or updates. Used to establish the WebSocket subscription on first call.

### Key methods

| Method | Purpose |
|--------|---------|
| `setConfig(config)` | Validate and store card config |
| `set hass(hass)` | Subscribe to `doorbell_ring` event on first call |
| `_fetchLastEvent()` | `GET /api/events?limit=1`, update internal state, re-render |
| `_render()` | Full DOM update from current state |
| `_relativeTime(iso)` | Convert ISO timestamp to "2m ago" string |
| `_startPolling()` | `setInterval` every 60s calling `_fetchLastEvent` |

### `getCardSize()`

Returns `3` — tells HA the card occupies approximately 3 grid rows.

---

## Error handling

- API fetch failures are caught and show an error state — no unhandled rejections
- Missing `url` config throws a clear error during `setConfig` so HA shows it in the card editor
- WebSocket subscription failure is silent (polling fallback covers it)
- Image load errors: `onerror` hides the `<img>` and shows a placeholder icon

---

## What is NOT in scope

- Card editor UI (the visual config editor in HA dashboard edit mode) — users configure via YAML
- Showing multiple recent rings — just the last one
- Face recognition data on the card
- Stats or binary sensor state
- HACS packaging
