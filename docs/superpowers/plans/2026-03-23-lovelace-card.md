# WhoRang Lovelace Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a single vanilla JS Lovelace custom card file that displays the last WhoRang doorbell ring (image, AI description, relative timestamp) and auto-updates via HA WebSocket events.

**Architecture:** One new file `doorbell-addon/web/static/js/whorang-card.js` — a plain `HTMLElement` subclass registered as `custom:whorang-card`. No backend changes needed; the addon already serves `/web/static/` and exposes `GET /api/events?limit=1`. The card subscribes to the `doorbell_ring` HA event for instant updates and falls back to 60-second polling.

**Tech Stack:** Vanilla JS ES2020, no build step, no dependencies. HA Lovelace custom card API (`setConfig`, `set hass`, `connectedCallback`, `disconnectedCallback`, `getCardSize`). Shadow DOM for style isolation.

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `doorbell-addon/web/static/js/whorang-card.js` | The complete card implementation |
| Modify | `doorbell-addon/CHANGELOG.md` | Document new feature |
| Modify | `doorbell-addon/config.yaml` | Version bump |
| Modify | `doorbell-addon/build.yaml` | Version bump |
| Modify | `doorbell-addon/requirements.txt` | Version comment bump |
| Modify | `doorbell-addon/src/config.py` | `app_version` ClassVar bump |

---

## Background: HA Lovelace Custom Card API

A Lovelace custom card is a `customElements.define`'d HTML element. HA calls these methods on it:

- `setConfig(config)` — called with the YAML config object. Throw here to show an error in the card editor. Called before `connectedCallback`.
- `set hass(hass)` — called on initial render and every time HA state changes. `hass.connection` has `.subscribeEvents(callback, eventType)` which returns a Promise resolving to an unsubscribe function.
- `connectedCallback()` — standard web component lifecycle, card added to DOM.
- `disconnectedCallback()` — card removed from DOM, clean up.
- `getCardSize()` — return a number hinting at card height in 50px grid rows.

The card must **not** use `document.createElement('ha-card')` inside a shadow root without attaching the shadow root first. Pattern:

```js
connectedCallback() {
  if (!this.shadowRoot) {
    this.attachShadow({ mode: 'open' });
  }
  this.shadowRoot.innerHTML = `...`;  // render into shadow root
}
```

HA CSS custom properties (like `--primary-text-color`) pierce Shadow DOM automatically.

---

## Background: WhoRang API

- **Endpoint:** `GET http://<whorang-ip>:8099/api/events?limit=1`
- **Response:** `{ "events": [{ "id": 1, "timestamp": "2026-03-23T14:00:00", "image_path": "/share/doorbell/images/doorbell_20260323.jpg", "ai_message": "A person in a blue jacket was at the door" }] }`
- **Image URL:** `http://<whorang-ip>:8099/api/images/<basename>` where `<basename> = image_path.split('/').pop()`
- **Event name:** `doorbell_ring` (fired by the addon after each processed ring)
- **CORS:** `allow_origins: ["*"]` — browser fetch from HA dashboard to port 8099 works without credentials.

---

## Task 1: Scaffold — class structure, constructor, registration

**Files:**
- Create: `doorbell-addon/web/static/js/whorang-card.js`

This task creates the skeleton: the class with all instance properties initialised to their default values, `getCardSize()`, and `customElements.define`. No rendering yet — just the structure that subsequent tasks fill in.

- [ ] **Step 1: Create the file with the class skeleton**

```js
// whorang-card.js — WhoRang Lovelace custom card
// Displays the last doorbell ring: image, AI description, timestamp.
// Auto-updates via HA WebSocket doorbell_ring event + 60s polling fallback.

class WhoRangCard extends HTMLElement {
  constructor() {
    super();
    // Config
    this._baseUrl = '';

    // State
    this._eventData = null;   // last fetched event object or null
    this._state = 'loading';  // 'loading' | 'no-events' | 'loaded' | 'error'

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
    // implemented in Task 2
  }

  connectedCallback() {
    // implemented in Task 2
  }

  disconnectedCallback() {
    // implemented in Task 4
  }

  set hass(hass) {
    // implemented in Task 4
  }

  _startPolling() {
    // implemented in Task 2
  }

  async _fetchLastEvent() {
    // implemented in Task 3
  }

  _render() {
    // implemented in Task 3
  }

  _updateTimestamp() {
    // implemented in Task 3
  }

  _relativeTime(iso) {
    // implemented in Task 3
  }
}

customElements.define('whorang-card', WhoRangCard);
```

- [ ] **Step 2: Verify the file is syntactically valid**

```bash
node --check doorbell-addon/web/static/js/whorang-card.js
```

Expected: no output (no errors). If `node` is not available, skip — syntax errors will surface in the browser in Task 5.

- [ ] **Step 3: Commit skeleton**

```bash
git add doorbell-addon/web/static/js/whorang-card.js
git commit -m "feat: scaffold whorang-card Lovelace custom element"
```

---

## Task 2: `setConfig`, `connectedCallback`, `_startPolling`

**Files:**
- Modify: `doorbell-addon/web/static/js/whorang-card.js`

- [ ] **Step 1: Implement `setConfig`**

Replace the `setConfig` stub:

```js
setConfig(config) {
  if (!config.url) {
    throw new Error('WhoRang card: "url" is required. Example: http://192.168.10.28:8099');
  }
  this._baseUrl = config.url.replace(/\/$/, '');  // strip trailing slash
  this.config = config;
}
```

- [ ] **Step 2: Implement `connectedCallback` with Shadow DOM and initial DOM structure**

Replace the `connectedCallback` stub:

```js
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
    window.open(`${this._baseUrl}/gallery`, '_blank');
  });

  this._render();
  this._startPolling();
}
```

- [ ] **Step 3: Implement `_startPolling`**

Replace the `_startPolling` stub:

```js
_startPolling() {
  // Idempotent — do nothing if already polling.
  if (this._pollInterval) return;
  // _fetchLastEvent resolves async and calls _render(), which recalculates
  // the timestamp. No need to call _updateTimestamp() separately here.
  this._pollInterval = setInterval(() => {
    this._fetchLastEvent();
  }, 60000);
}
```

- [ ] **Step 4: Syntax check**

```bash
node --check doorbell-addon/web/static/js/whorang-card.js
```

- [ ] **Step 5: Commit**

```bash
git add doorbell-addon/web/static/js/whorang-card.js
git commit -m "feat: implement setConfig, connectedCallback, and polling for whorang-card"
```

---

## Task 3: `_fetchLastEvent`, `_render`, `_relativeTime`, `_updateTimestamp`

**Files:**
- Modify: `doorbell-addon/web/static/js/whorang-card.js`

This is the core rendering logic. After this task the card can display all states.

- [ ] **Step 1: Add `_escapeHtml` helper**

Add this method to the class (alongside the other methods). `ai_message` comes from the API and is injected into `innerHTML`; it must be escaped to prevent broken markup.

```js
_escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
```

- [ ] **Step 2: Implement `_relativeTime`**

Replace the `_relativeTime` stub:

```js
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
```

- [ ] **Step 3: Implement `_fetchLastEvent`**

Replace the `_fetchLastEvent` stub:

```js
async _fetchLastEvent() {
  if (!this._baseUrl) return;
  try {
    const resp = await fetch(`${this._baseUrl}/api/events?limit=1`);
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
    this._eventData = null;
  }
  this._render();
}
```

- [ ] **Step 4: Implement `_render`**

Replace the `_render` stub:

```js
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
      <div class="state-message">Unable to reach WhoRang</div>
    `;
    return;
  }

  // Loaded state
  const ev = this._eventData;
  const basename = ev.image_path ? ev.image_path.split('/').pop() : '';
  const hasImage = basename !== '';
  const imageUrl = hasImage ? `${this._baseUrl}/api/images/${basename}` : '';
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
```

- [ ] **Step 4: Implement `_updateTimestamp`**

Replace the `_updateTimestamp` stub:

```js
_updateTimestamp() {
  // No-op if no event loaded yet.
  if (!this._eventData) return;
  const el = this.shadowRoot && this.shadowRoot.querySelector('#wr-timestamp');
  if (el) el.textContent = this._relativeTime(this._eventData.timestamp);
}
```

- [ ] **Step 5: Syntax check**

```bash
node --check doorbell-addon/web/static/js/whorang-card.js
```

- [ ] **Step 6: Commit**

```bash
git add doorbell-addon/web/static/js/whorang-card.js
git commit -m "feat: implement rendering and data fetching for whorang-card"
```

---

## Task 4: `set hass` and `disconnectedCallback`

**Files:**
- Modify: `doorbell-addon/web/static/js/whorang-card.js`

- [ ] **Step 1: Implement `set hass`**

Replace the `set hass` stub:

```js
set hass(hass) {
  // Guard — only act on the first hass assignment.
  if (this._subscribed) return;
  this._subscribed = true;

  // Fetch immediately on first assignment.
  this._fetchLastEvent();

  // Subscribe to doorbell_ring HA events for instant updates.
  // The payload is intentionally ignored — a fresh fetch avoids DB write races.
  try {
    hass.connection
      .subscribeEvents(() => { this._fetchLastEvent(); }, 'doorbell_ring')
      .then((unsub) => { this._unsubscribeEvent = unsub; })
      .catch(() => { /* silent — polling covers it */ });
  } catch (_) {
    // subscribeEvents not available — polling covers it.
  }
}
```

- [ ] **Step 2: Implement `disconnectedCallback`**

Replace the `disconnectedCallback` stub:

```js
disconnectedCallback() {
  this._unsubscribeEvent();
  if (this._pollInterval) {
    clearInterval(this._pollInterval);
    this._pollInterval = null;
  }
  // Reset subscription flag so set hass re-subscribes if the card is re-inserted.
  this._subscribed = false;
}
```

- [ ] **Step 3: Syntax check**

```bash
node --check doorbell-addon/web/static/js/whorang-card.js
```

- [ ] **Step 4: Commit**

```bash
git add doorbell-addon/web/static/js/whorang-card.js
git commit -m "feat: implement hass setter and cleanup for whorang-card"
```

---

## Task 5: Manual browser verification

This is a plain JS file with no automated test runner. Verification is done in the browser against a real HA instance.

**Pre-requisites:** WhoRang addon is running and accessible at `http://<ip>:8099`.

- [ ] **Step 1: Register the card as a Lovelace resource**

In HA → Settings → Dashboards → Resources → Add resource:
- URL: `http://<whorang-ip>:8099/static/js/whorang-card.js`
- Resource type: JavaScript module

If the resource was already registered from a previous attempt, delete it and re-add to force a cache bust.

- [ ] **Step 2: Add the card to a dashboard**

Edit any dashboard, add a Manual card:

```yaml
type: custom:whorang-card
url: http://<whorang-ip>:8099
```

- [ ] **Step 3: Verify loaded state**

Expected: card shows last ring image, AI description, relative timestamp. No console errors in browser DevTools.

- [ ] **Step 4: Verify error state**

Temporarily change the card config to a non-existent URL:

```yaml
type: custom:whorang-card
url: http://192.168.10.99:8099
```

Expected: card shows "Unable to reach WhoRang". No unhandled promise rejections in console.

Revert to correct URL.

- [ ] **Step 5: Verify click behaviour**

Click anywhere on the card. Expected: WhoRang gallery opens in a new browser tab.

- [ ] **Step 6: Verify auto-update on ring**

Trigger a doorbell ring (via WhoRang test or physical button). Expected: card updates within a few seconds without page refresh.

- [ ] **Step 7: Verify no-events state (optional)**

If a fresh WhoRang instance with no events is available, add the card and confirm it shows "No rings recorded yet".

---

## Task 6: Version bump and CHANGELOG

**Files:**
- Modify: `doorbell-addon/CHANGELOG.md`
- Modify: `doorbell-addon/config.yaml`
- Modify: `doorbell-addon/build.yaml`
- Modify: `doorbell-addon/requirements.txt`
- Modify: `doorbell-addon/src/config.py`

Current version: `1.0.153`. New version: `1.0.154`.

- [ ] **Step 1: Update version in all five files**

`doorbell-addon/config.yaml`: change `version: "1.0.153"` → `version: "1.0.154"`

`doorbell-addon/build.yaml`: change both `1.0.153` occurrences → `1.0.154`

`doorbell-addon/requirements.txt`: change `# Version: 1.0.153` → `# Version: 1.0.154`

`doorbell-addon/src/config.py`: change `app_version: ClassVar[str] = "1.0.153"` → `"1.0.154"`

- [ ] **Step 2: Add CHANGELOG entry**

In `doorbell-addon/CHANGELOG.md`, add at the top (after the header, before the current `## [1.0.153]` entry):

```markdown
## [1.0.154] - 2026-03-23

### Added
- **Lovelace custom card** (`custom:whorang-card`) — displays the last doorbell ring (image, AI description, relative timestamp) on any HA dashboard. Auto-updates via the `doorbell_ring` HA event; 60-second polling fallback. Served directly from the addon at `/static/js/whorang-card.js`. Add as a Lovelace resource and configure with `url: http://<whorang-ip>:8099`.
```

- [ ] **Step 3: Commit and tag**

```bash
git add doorbell-addon/CHANGELOG.md doorbell-addon/config.yaml doorbell-addon/build.yaml \
        doorbell-addon/requirements.txt doorbell-addon/src/config.py
git commit -m "feat: release v1.0.154 — Lovelace custom card"
git tag v1.0.154
git push && git push --tags
```

---

## Complete file: `whorang-card.js`

After all tasks, the complete file should look like this (for reference):

```js
// whorang-card.js — WhoRang Lovelace custom card
// Displays the last doorbell ring: image, AI description, timestamp.
// Auto-updates via HA WebSocket doorbell_ring event + 60s polling fallback.

class WhoRangCard extends HTMLElement {
  constructor() {
    super();
    this._baseUrl = '';
    this._eventData = null;
    this._state = 'loading';
    this._subscribed = false;
    this._unsubscribeEvent = () => {};
    this._pollInterval = null;
  }

  getCardSize() { return 5; }

  setConfig(config) {
    if (!config.url) {
      throw new Error('WhoRang card: "url" is required. Example: http://192.168.10.28:8099');
    }
    this._baseUrl = config.url.replace(/\/$/, '');
    this.config = config;
  }

  connectedCallback() {
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { overflow: hidden; cursor: pointer; }
        .header { display: flex; align-items: center; gap: 8px; padding: 12px 16px 8px; font-weight: 500; color: var(--primary-text-color); }
        .header ha-icon { --mdc-icon-size: 20px; color: var(--primary-color, #03a9f4); }
        .image-wrapper { position: relative; width: 100%; aspect-ratio: 16 / 9; background: var(--secondary-background-color, #1c1c1f); overflow: hidden; }
        .image-wrapper img { width: 100%; height: 100%; object-fit: cover; display: block; }
        .placeholder-icon { display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; color: var(--secondary-text-color, #888); }
        .placeholder-icon ha-icon { --mdc-icon-size: 48px; }
        .body { padding: 12px 16px; }
        .description { color: var(--primary-text-color); font-size: 14px; line-height: 1.4; margin-bottom: 4px; }
        .timestamp { color: var(--secondary-text-color, #888); font-size: 12px; text-align: right; }
        .state-message { padding: 24px 16px; text-align: center; color: var(--secondary-text-color, #888); font-size: 14px; }
        .spinner { display: flex; justify-content: center; padding: 24px; }
      </style>
      <ha-card></ha-card>
    `;
    this.shadowRoot.querySelector('ha-card').addEventListener('click', () => {
      window.open(`${this._baseUrl}/gallery`, '_blank');
    });
    this._render();
    this._startPolling();
  }

  disconnectedCallback() {
    this._unsubscribeEvent();
    if (this._pollInterval) { clearInterval(this._pollInterval); this._pollInterval = null; }
    this._subscribed = false;
  }

  _escapeHtml(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  set hass(hass) {
    if (this._subscribed) return;
    this._subscribed = true;
    this._fetchLastEvent();
    try {
      hass.connection
        .subscribeEvents(() => { this._fetchLastEvent(); }, 'doorbell_ring')
        .then((unsub) => { this._unsubscribeEvent = unsub; })
        .catch(() => {});
    } catch (_) {}
  }

  _startPolling() {
    if (this._pollInterval) return;
    this._pollInterval = setInterval(() => { this._fetchLastEvent(); }, 60000);
  }

  async _fetchLastEvent() {
    if (!this._baseUrl) return;
    try {
      const resp = await fetch(`${this._baseUrl}/api/events?limit=1`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      if (!data.events || data.events.length === 0) {
        this._state = 'no-events'; this._eventData = null;
      } else {
        this._state = 'loaded'; this._eventData = data.events[0];
      }
    } catch (_) {
      this._state = 'error'; this._eventData = null;
    }
    this._render();
  }

  _render() {
    const card = this.shadowRoot && this.shadowRoot.querySelector('ha-card');
    if (!card) return;
    if (this._state === 'loading') {
      card.innerHTML = `<div class="header"><ha-icon icon="mdi:doorbell"></ha-icon> WhoRang — Last Ring</div><div class="spinner"><ha-circular-progress active></ha-circular-progress></div>`;
      return;
    }
    if (this._state === 'no-events') {
      card.innerHTML = `<div class="header"><ha-icon icon="mdi:doorbell"></ha-icon> WhoRang — Last Ring</div><div class="state-message">No rings recorded yet</div>`;
      return;
    }
    if (this._state === 'error') {
      card.innerHTML = `<div class="header"><ha-icon icon="mdi:doorbell"></ha-icon> WhoRang — Last Ring</div><div class="state-message">Unable to reach WhoRang</div>`;
      return;
    }
    const ev = this._eventData;
    const basename = ev.image_path ? ev.image_path.split('/').pop() : '';
    const hasImage = basename !== '';
    const imageUrl = hasImage ? `${this._baseUrl}/api/images/${basename}` : '';
    const description = this._escapeHtml(ev.ai_message || 'No description available');
    const timestamp = this._relativeTime(ev.timestamp);
    const imageHtml = hasImage
      ? `<img src="${imageUrl}" alt="Doorbell image" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
      : '';
    const placeholderHtml = `<div class="placeholder-icon" style="${hasImage ? 'display:none' : ''}"><ha-icon icon="mdi:camera-off"></ha-icon></div>`;
    card.innerHTML = `
      <div class="header"><ha-icon icon="mdi:doorbell"></ha-icon> WhoRang — Last Ring</div>
      <div class="image-wrapper">${imageHtml}${placeholderHtml}</div>
      <div class="body">
        <div class="description">${description}</div>
        <div class="timestamp" id="wr-timestamp">${timestamp}</div>
      </div>
    `;
  }

  _updateTimestamp() {
    if (!this._eventData) return;
    const el = this.shadowRoot && this.shadowRoot.querySelector('#wr-timestamp');
    if (el) el.textContent = this._relativeTime(this._eventData.timestamp);
  }

  _relativeTime(iso) {
    const diffSecs = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (diffSecs < 30) return 'just now';
    if (diffSecs < 90) return '1m ago';
    const mins = Math.round(diffSecs / 60);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.round(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.round(hours / 24)}d ago`;
  }
}

customElements.define('whorang-card', WhoRangCard);
```
