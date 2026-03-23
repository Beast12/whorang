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
