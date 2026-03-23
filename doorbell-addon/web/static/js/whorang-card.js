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
    if (!config.url) {
      throw new Error('WhoRang card: "url" is required. Example: http://192.168.10.28:8099');
    }
    this._baseUrl = config.url.replace(/\/$/, '');  // strip trailing slash
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
      window.open(`${this._baseUrl}/gallery`, '_blank');
    });

    this._render();
    this._startPolling();
  }

  disconnectedCallback() {
    // implemented in Task 4
  }

  set hass(hass) {
    // implemented in Task 4
  }

  _startPolling() {
    // Idempotent — do nothing if already polling.
    if (this._pollInterval) return;
    // _fetchLastEvent resolves async and calls _render(), which recalculates
    // the timestamp. No need to call _updateTimestamp() separately here.
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
