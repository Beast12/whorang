# WhoRang Card — Read from hass.states (no HTTP)

**Date:** 2026-04-03  
**Status:** Approved  
**Context:** Every HTTP approach to the add-on's ingress URL fails with 401 (HA blocks all `/api/hassio/` REST calls for this user). The fix is architectural: push last-event data into HA sensor attributes and serve the latest image via `/local/`, eliminating all HTTP calls from the card.

---

## Problem

`whorang-card.js` currently:
1. Discovers the add-on's ingress URL via WebSocket `supervisor/api` (works)
2. Calls `fetch(ingressUrl/api/events)` to get the last event (fails — 401)
3. Uses `<img src="${ingressUrl}/api/images/...">` (would also fail — 401)

Root cause: HA's ingress proxy requires an `ingress_session` cookie. Establishing it requires `POST /api/hassio/ingress/session`, which also returns 401. All `/api/hassio/` REST endpoints are blocked for this user.

---

## Solution

Push last-event data from the add-on into HA sensor attributes. The card reads `hass.states` — no HTTP calls, no auth, works everywhere HA works.

---

## Architecture

### Backend: `ha_integration.py`

**Entity names (corrected from README):**
- `sensor.doorbell_last_event` — last ring timestamp + new attributes
- `sensor.doorbell_total_events` — total ring count
- `binary_sensor.doorbell_person_detected` — person detected within 30s

**New attributes on `sensor.doorbell_last_event`:**

| Attribute | Type | Value |
|-----------|------|-------|
| `event_id` | int or `null` | ID of the last event |
| `description` | string | `ai_message` or `""` if none |
| `image_url` | string | `/local/whorang_latest.jpg?t={event_id}` or `""` if no image |

**Image copy:** In `update_sensors()`, after fetching `last_event`:
- If `last_event.image_path` exists as a file, copy it to `/config/www/whorang_latest.jpg`
- Use `shutil.copy2` — silent fail (log warning, don't raise)
- The `/config/www/` directory is already created by `run.sh`

### Frontend: `whorang-card.js`

**Removed entirely:**
- `_ingressUrl`, `_subscribed`, `_unsubscribeEvent`, `_pollInterval`
- `_discoverAndInit()`, `_fetchLastEvent()`, `_startPolling()`
- All `hass.connection.sendMessagePromise` calls
- All `fetch()` calls

**New logic in `set hass(hass)`:**
- Read `hass.states['sensor.doorbell_last_event']`
- Compare `attributes.event_id` to `this._lastEventId`
- Skip re-render if nothing changed
- Update `this._lastEventId` and call `_render()`

**States:**
- `loading` — sensor not yet in hass.states (initial render before hass)
- `no-events` — sensor state is `"unknown"` or attributes.event_id is null
- `loaded` — valid event_id present
- (no `error` state needed — sensor is always available once HA starts)

**Render (loaded):**
- Image: `<img src="${attributes.image_url}">` — no auth needed (`/local/` is public)
- Description: `attributes.description` or `"No description"`
- Timestamp: `_relativeTime(stateValue)` (the sensor's state is the ISO timestamp)
- Click: open WhoRang sidebar panel via `window.open('/hassio/ingress/{slug}', '_blank')` using slug from `hass.panels`

### README / DOCS fixes

Update both files to use the correct entity IDs:
- `sensor.doorbell_last_event` (not `sensor.whorang_last_event_id`)
- `sensor.doorbell_total_events` (not `sensor.whorang_total_events`)
- `binary_sensor.doorbell_person_detected` (not `sensor.whorang_last_event_time`)

---

## Data Flow

```
Doorbell rings
  → app.py saves event to SQLite
  → ha_integration.handle_doorbell_ring()
    → update_sensors()
      → copies image to /config/www/whorang_latest.jpg
      → pushes sensor.doorbell_last_event with attributes {event_id, description, image_url}
      → HA broadcasts state change via WebSocket
  → whorang-card.js set hass() triggered
    → reads hass.states['sensor.doorbell_last_event'].attributes
    → re-renders card with new image and description
```

---

## Error Handling

- Image copy fails: log warning, set `image_url: ""`, card shows placeholder icon
- Sensor state is `"unknown"`: card shows "No rings recorded yet"
- Sensor missing from hass.states: card shows spinner (loading)

---

## Out of Scope

- Gallery page — still accessed via ingress sidebar panel (browser navigation, not fetch)
- Multiple images — card only shows the latest ring
- Older image retrieval — gallery handles that via the sidebar panel

---

## Files Changed

| File | Change |
|------|--------|
| `doorbell-addon/src/ha_integration.py` | Add attributes + image copy in `update_sensors()` |
| `doorbell-addon/web/static/js/whorang-card.js` | Rewrite: read hass.states, remove all HTTP |
| `README.md` | Fix sensor entity IDs |
| `doorbell-addon/DOCS.md` | Fix sensor entity IDs |
| `doorbell-addon/CHANGELOG.md` | Add v1.0.160 entry |
| `doorbell-addon/config.yaml` + `build.yaml` + `requirements.txt` + `src/config.py` | Bump to 1.0.160 |
