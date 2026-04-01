# WhoRang Card — Remote Access via HA Ingress

**Date:** 2026-04-01
**Status:** Approved

---

## Problem

The existing `whorang-card.js` Lovelace card makes direct HTTP calls to `http://<local-ip>:8099`. This works only on the local network. When HA is accessed remotely (Nabu Casa, reverse proxy, VPN-less), the card fails — it shows "Unable to reach WhoRang" because the browser cannot reach a private IP from outside the network. HTTPS deployments also break due to mixed-content blocking.

---

## Solution Overview

Route all card API calls through HA's ingress proxy instead of directly to the add-on's IP/port. The add-on already has `ingress: true` and `ingress_port: 8099` in `config.yaml`, so HA already proxies the add-on — the card just wasn't using it.

Two complementary changes:

1. **JS file served by HA directly** — add-on copies `whorang-card.js` to `/config/www/` on startup. Resource URL becomes `/local/whorang-card.js` (served by HA, no token, works everywhere).
2. **Runtime API calls through ingress** — card auto-discovers the ingress URL via `hass.callApi`, then uses relative paths for all fetches.

---

## Architecture

### 1. Static file delivery (resource URL)

On add-on startup, `run.sh` copies the file before launching uvicorn:

```
/app/web/static/js/whorang-card.js  →  /config/www/whorang-card.js
```

HA serves `/config/www/` at `/local/`. The Lovelace resource is registered once as:

```
/local/whorang-card.js
```

This URL is stable across add-on updates (the file is overwritten on each start), has no token, and works identically from any network.

`config:rw` is already present in `config.yaml`'s `map` section, so no config change is needed.

### 2. Runtime ingress discovery

On first `hass` assignment, the card calls:

```js
const info = await hass.callApi('GET', 'hassio/addons/whorang/info');
this._ingressUrl = info.data.ingress_url; // e.g. "/api/hassio_ingress/abc123"
```

`hass.callApi` is an authenticated HA method available in all Lovelace custom cards. It works locally and remotely (Nabu Casa, reverse proxy) because it routes through the HA frontend's existing connection.

The ingress URL is cached as `this._ingressUrl`. All subsequent API calls use it as a relative path prefix:

| Purpose | URL |
|---------|-----|
| Fetch latest event | `fetch(this._ingressUrl + '/api/events?limit=1')` |
| Image src | `this._ingressUrl + '/api/images/' + basename` |
| Gallery click | `window.open(this._ingressUrl + '/gallery', '_blank')` |

Relative paths resolve correctly whether HA is accessed on the local network, via Nabu Casa, or any reverse proxy.

### 3. Backend

No backend changes needed. HA strips the ingress prefix before forwarding to the add-on, so the app continues receiving `/api/events`, `/api/images/...` as before. The existing `IngressAuthMiddleware` already handles ingress headers.

---

## Card Lifecycle Changes

### `setConfig`

- `url` config key is no longer required, read, or validated
- `setConfig` stores `this.config = config` only
- Existing card YAML with `url:` silently ignores the value (no error)

### `set hass` (new flow)

```
1. Guard: if _subscribed, return
2. Set _subscribed = true
3. Call _discoverAndInit(hass) — async, not awaited
   Inside _discoverAndInit:
     a. hass.callApi('GET', 'hassio/addons/whorang/info')
     b. Extract data.ingress_url → store as this._ingressUrl
     c. Call _fetchLastEvent()
     d. Subscribe to doorbell_ring event
     e. On any error → set state = 'error', call _render()
```

Card stays in `'loading'` state (spinner) while discovery runs. If discovery fails, transitions to `'error'`.

### `_fetchLastEvent` guard

`if (!this._ingressUrl) return` — prevents fetch attempts before discovery completes.

### New error message

Discovery failure renders: **"WhoRang add-on not found"** — distinct from the existing **"Unable to reach WhoRang"** (which covers fetch errors after discovery succeeds).

### Unchanged

- Polling (60s `setInterval`, started in `connectedCallback`)
- WebSocket subscription lifecycle
- `disconnectedCallback` cleanup
- `_render()` and all display states
- `_relativeTime()`
- `getCardSize()`

---

## Property changes

| Old | New | Notes |
|-----|-----|-------|
| `_baseUrl` | `_ingressUrl` | `null` until discovery completes |

`hass` is passed directly to `_discoverAndInit(hass)` and not stored on the instance.

---

## User Setup

### New users

1. Register Lovelace resource: **`/local/whorang-card.js`** (Type: JavaScript module)
2. Add card to dashboard:
   ```yaml
   type: custom:whorang-card
   ```
3. Done — works locally and remotely.

### Existing users (migration)

1. In HA → Settings → Dashboards → Resources: replace the old `http://192.168.x.x:8099/static/js/whorang-card.js` entry with `/local/whorang-card.js`
2. Remove `url:` from card YAML (or leave it — it's ignored)
3. Restart the add-on once so it copies the file to `/config/www/`

---

## Error States

| Situation | State | Message |
|-----------|-------|---------|
| Discovery in progress | `loading` | Spinner |
| Discovery failed (not a Supervisor install, wrong slug, etc.) | `error` | "WhoRang add-on not found" |
| Fetch failed after discovery | `error` | "Unable to reach WhoRang" |
| No events yet | `no-events` | "No rings recorded yet" |
| Loaded | `loaded` | Image + description + timestamp |

---

## Out of Scope

- Card editor UI
- Multiple recent rings
- Face recognition data on the card
- HACS packaging
- Non-Supervisor HA installs (HA Container / HA Core — these cannot run add-ons anyway)
