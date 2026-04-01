# Widget Remote Access via HA Ingress — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `whorang-card.js` work from any network by routing through HA ingress instead of the local IP.

**Architecture:** `run.sh` copies the card JS to `/config/www/` on startup so HA serves it at `/local/whorang-card.js`. At runtime the card calls `hass.callApi('GET', 'hassio/addons/whorang/info')` to discover the ingress URL, then uses it as a relative path prefix for all fetches. No backend changes required.

**Tech Stack:** Vanilla JS (card), bash (run.sh), no new dependencies.

---

## File Map

| File | Change |
|------|--------|
| `doorbell-addon/run.sh` | Add `mkdir -p /config/www && cp` before uvicorn start |
| `doorbell-addon/web/static/js/whorang-card.js` | Full rewrite of URL handling: drop `url` config, add `_discoverAndInit`, replace `_baseUrl` with `_ingressUrl` |
| `CHANGELOG.md` | Add entry |

---

## Task 1: Copy card to `/config/www/` on startup

**Files:**
- Modify: `doorbell-addon/run.sh:58-60`

- [ ] **Step 1: Add the copy command to `run.sh`**

Open `doorbell-addon/run.sh`. Before the final `exec python3 -m uvicorn ...` line, add:

```bash
# Copy Lovelace card to HA www folder — served at /local/whorang-card.js
mkdir -p /config/www
cp /app/web/static/js/whorang-card.js /config/www/whorang-card.js
bashio::log.info "Lovelace card copied to /config/www/whorang-card.js"
```

The file should end as:

```bash
# Copy Lovelace card to HA www folder — served at /local/whorang-card.js
mkdir -p /config/www
cp /app/web/static/js/whorang-card.js /config/www/whorang-card.js
bashio::log.info "Lovelace card copied to /config/www/whorang-card.js"

# Start the application
cd /app
exec python3 -m uvicorn src.app:app --host 0.0.0.0 --port 8099 --log-level info
```

- [ ] **Step 2: Verify the script is still syntactically valid**

```bash
bash -n doorbell-addon/run.sh
```

Expected: no output (exit 0).

- [ ] **Step 3: Commit**

```bash
git add doorbell-addon/run.sh
git commit -m "feat: copy whorang-card.js to /config/www on startup"
```

---

## Task 2: Rewrite card for ingress auto-discovery

**Files:**
- Modify: `doorbell-addon/web/static/js/whorang-card.js`

- [ ] **Step 1: Replace the entire file**

Replace `doorbell-addon/web/static/js/whorang-card.js` with the following:

```js
// whorang-card.js — WhoRang Lovelace custom card
// Displays the last doorbell ring: image, AI description, timestamp.
// Auto-updates via HA WebSocket doorbell_ring event + 60s polling fallback.
// Served by HA at /local/whorang-card.js (copied by run.sh on startup).
// Uses HA ingress for all API calls — works on any network.

class WhoRangCard extends HTMLElement {
  constructor() {
    super();
    // Ingress URL discovered at runtime via hass.callApi (e.g. "/api/hassio_ingress/abc123")
    this._ingressUrl = null;

    // State
    this._eventData = null;   // last fetched event object or null
    this._state = 'loading';  // 'loading' | 'no-events' | 'loaded' | 'error'
    this._errorMessage = '';  // displayed in error state

    // WebSocket subscription
    this._subscribed = false;
    this._unsubscribeEvent = () => {};  // no-op until subscribeEvents resolves

    // Polling
    this._pollInterval = null;
  }

  getCardSize() {
    // 16:9 image + header + description ≈ 5 grid rows (~250px). Layout hint only.
    return 5;
  }

  setConfig(config) {
    // url is no longer required — ingress URL is discovered automatically.
    // Existing card YAML with url: set will silently ignore the value.
    this.config = config;
  }

  connectedCallback() {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: 'open' });
    }
    // Build initial DOM (loading state); _render() will update it.
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

    // Open WhoRang gallery on click anywhere on the card.
    this.shadowRoot.querySelector('ha-card').addEventListener('click', () => {
      if (this._ingressUrl) window.open(`${this._ingressUrl}/gallery`, '_blank');
    });

    this._render();
    this._startPolling();
  }

  disconnectedCallback() {
    this._unsubscribeEvent();
    if (this._pollInterval) {
      clearInterval(this._pollInterval);
      this._pollInterval = null;
    }
    // Reset subscription flag so set hass re-subscribes if the card is re-inserted.
    this._subscribed = false;
  }

  set hass(hass) {
    // Guard — only act on the first hass assignment.
    if (this._subscribed) return;
    this._subscribed = true;
    this._discoverAndInit(hass);
  }

  async _discoverAndInit(hass) {
    // Discover ingress URL from HA Supervisor, then fetch and subscribe.
    try {
      const info = await hass.callApi('GET', 'hassio/addons/whorang/info');
      this._ingressUrl = info.data.ingress_url;
    } catch (_) {
      this._state = 'error';
      this._errorMessage = 'WhoRang add-on not found';
      this._render();
      return;
    }

    // Fetch immediately after discovery.
    await this._fetchLastEvent();

    // Subscribe to doorbell_ring HA events for instant updates.
    try {
      hass.connection
        .subscribeEvents(() => { this._fetchLastEvent(); }, 'doorbell_ring')
        .then((unsub) => { this._unsubscribeEvent = unsub; })
        .catch(() => { /* silent — polling covers it */ });
    } catch (_) {
      // subscribeEvents not available — polling covers it.
    }
  }

  _startPolling() {
    // Idempotent — do nothing if already polling.
    if (this._pollInterval) return;
    this._pollInterval = setInterval(() => {
      this._fetchLastEvent();
    }, 60000);
  }

  _escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  async _fetchLastEvent() {
    if (!this._ingressUrl) return;
    try {
      const resp = await fetch(`${this._ingressUrl}/api/events?limit=1`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      if (!data.events || data.events.length === 0) {
        this._state = 'no-events';
        this._eventData = null;
      } else {
        this._state = 'loaded';
        this._eventData = data.events[0];
      }
    } catch (err) {
      this._state = 'error';
      this._errorMessage = 'Unable to reach WhoRang';
      this._eventData = null;
    }
    this._render();
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

    if (this._state === 'error') {
      card.innerHTML = `
        <div class="header"><ha-icon icon="mdi:doorbell"></ha-icon> WhoRang — Last Ring</div>
        <div class="state-message">${this._escapeHtml(this._errorMessage)}</div>
      `;
      return;
    }

    // Loaded state
    const ev = this._eventData;
    const basename = ev.image_path ? ev.image_path.split('/').pop() : '';
    const hasImage = basename !== '';
    const imageUrl = hasImage ? `${this._ingressUrl}/api/images/${basename}` : '';
    const description = this._escapeHtml(ev.ai_message || 'No description available');
    const timestamp = this._relativeTime(ev.timestamp);

    const imageHtml = hasImage
      ? `<img src="${imageUrl}" alt="Doorbell image"
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
        <div class="timestamp" id="wr-timestamp">${timestamp}</div>
      </div>
    `;
  }

  _updateTimestamp() {
    // No-op if no event loaded yet.
    if (!this._eventData) return;
    const el = this.shadowRoot && this.shadowRoot.querySelector('#wr-timestamp');
    if (el) el.textContent = this._relativeTime(this._eventData.timestamp);
  }

  _relativeTime(iso) {
    const now = Date.now();
    const then = new Date(iso).getTime();
    const diffMs = now - then;
    const diffSecs = Math.floor(diffMs / 1000);
    if (diffSecs < 30) return 'just now';
    if (diffSecs < 90) return '1m ago';
    const diffMins = Math.round(diffSecs / 60);
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.round(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.round(diffHours / 24);
    return `${diffDays}d ago`;
  }
}

customElements.define('whorang-card', WhoRangCard);
```

- [ ] **Step 2: Verify the diff looks right**

Run:
```bash
git diff doorbell-addon/web/static/js/whorang-card.js
```

Confirm:
- `_baseUrl` is gone, replaced with `_ingressUrl = null`
- `setConfig` no longer throws on missing `url`
- `_discoverAndInit` calls `hass.callApi('GET', 'hassio/addons/whorang/info')`
- `_fetchLastEvent` guard is `if (!this._ingressUrl) return`
- Error state renders `this._errorMessage` (not a hardcoded string)
- Gallery click is guarded: `if (this._ingressUrl) window.open(...)`

- [ ] **Step 3: Commit**

```bash
git add doorbell-addon/web/static/js/whorang-card.js
git commit -m "feat: use HA ingress for whorang-card — works on any network"
```

---

## Task 3: Update CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Check current CHANGELOG format**

```bash
head -40 CHANGELOG.md
```

- [ ] **Step 2: Add entry at the top (after the header)**

Add the following block immediately after the `# Changelog` header line, before any existing `## [x.y.z]` entry:

```markdown
## [Unreleased]

### Changed
- `whorang-card.js` now works on any network (remote, Nabu Casa, reverse proxy). All API calls are routed through HA ingress instead of directly to the local IP.
- Lovelace resource URL changes from `http://<ip>:8099/static/js/whorang-card.js` to `/local/whorang-card.js` (the add-on now copies the file to `/config/www/` on startup).
- Card YAML no longer requires a `url:` field — removed entirely.
```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "chore: update changelog for ingress-based card"
```

---

## Verification Checklist (manual, in HA)

After deploying the updated add-on:

1. **Restart the add-on** — check add-on log for: `Lovelace card copied to /config/www/whorang-card.js`
2. **Update Lovelace resource** — Settings → Dashboards → Resources: replace old entry with `/local/whorang-card.js`
3. **Update card YAML** — remove `url:` line (or leave it; it is silently ignored)
4. **Hard-reload HA** — Ctrl+Shift+R in browser
5. **Local test** — card should load and show last ring
6. **Remote test** — open HA via Nabu Casa or external URL; card should load and show last ring
7. **Error state** — temporarily disconnect from HA Supervisor (not practical) OR verify by renaming the add-on slug — card should show "WhoRang add-on not found"
