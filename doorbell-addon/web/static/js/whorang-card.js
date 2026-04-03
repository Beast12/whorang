// whorang-card.js — WhoRang Lovelace custom card
// Displays the last doorbell ring: image, AI description, timestamp.
// Auto-updates via HA WebSocket doorbell_ring event + 60s polling fallback.
// Served by HA at /local/whorang-card.js (copied by run.sh on startup).
// Discovers ingress URL automatically via HA WebSocket supervisor/api.

class WhoRangCard extends HTMLElement {
  constructor() {
    super();
    // Discovered at runtime via HA WebSocket supervisor/api
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
    // Discover ingress URL via HA's WebSocket supervisor/api channel.
    // Step 1: find the full addon slug from hass.panels (no API call needed).
    // Custom-repo add-ons have a hash prefix, e.g. "a48cb117_whorang".
    try {
      const panel = Object.values(hass.panels || {}).find(p => {
        const path = p.url_path || '';
        return path === 'whorang' || path.endsWith('_whorang');
      });
      const slug = panel ? panel.url_path : 'whorang';

      // Step 2: fetch addon info via WebSocket supervisor/api.
      const info = await hass.connection.sendMessagePromise({
        type: 'supervisor/api',
        endpoint: `/addons/${slug}/info`,
        method: 'GET',
      });

      const url = (info && info.ingress_url) || (info && info.data && info.data.ingress_url);
      if (!url) throw new Error('ingress_url missing from supervisor response');
      this._ingressUrl = url.replace(/\/$/, '');

      // Step 3: establish ingress session cookie so fetch() and <img> can authenticate.
      // This is what HA's own frontend does before loading any ingress panel.
      await hass.callApi('POST', 'hassio/ingress/session');
    } catch (err) {
      console.error('[WhoRang] discovery failed:', err);
      this._state = 'error';
      this._errorMessage = 'WhoRang add-on not found';
      this._render();
      return;
    }

    // Step 3: fetch and subscribe now that we have the ingress URL.
    await this._fetchLastEvent();

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
        <div class="state-message">${this._escapeHtml(this._errorMessage || 'Unknown error')}</div>
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
