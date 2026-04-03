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
