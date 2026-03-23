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
