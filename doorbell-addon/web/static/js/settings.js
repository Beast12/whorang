// Settings page JavaScript functionality

const API = {
    settings: 'api/settings',
    cameras: 'api/cameras',
    weatherEntities: 'api/weather-entities',
    cameraTest: 'api/camera/test',
    notifyServices: 'api/settings/notify-services',
    binarySensors: 'api/settings/binary-sensors',
    llmvisionProviders: 'api/settings/llmvision-providers',
};

document.addEventListener('DOMContentLoaded', function() {
    initializeSettings();
});

function initializeSettings() {
    setupCameraSourceToggle();

    loadCurrentSettings().then(data => {
        loadDropdownOptions(
            'camera-entity',
            API.cameras,
            data => data.cameras || [],
            c => ({ value: c.entity_id, label: c.friendly_name }),
            'No cameras found',
            'Error loading cameras'
        );
        loadDropdownOptions(
            'weather-entity',
            API.weatherEntities,
            data => data.entities || [],
            e => ({ value: e.entity_id, label: e.friendly_name }),
            'No weather entities found',
            'Error loading weather entities'
        );
        updateCameraStatus();
        window._currentNotifyServices = (data && data.ha_notify_services) || [];
        loadNotifyServices();
        loadLlmvisionProviders();
        loadDropdownOptions(
            'trigger-entity',
            API.binarySensors,
            data => data.entities || [],
            e => ({ value: e.entity_id, label: e.friendly_name }),
            'No binary sensors found',
            'Error loading sensors'
        );
        checkAiPublicPathWarning();
    });

    const llmToggle = document.getElementById('llmvision-enabled');
    if (llmToggle) llmToggle.addEventListener('change', checkAiPublicPathWarning);
}

function setupCameraSourceToggle() {
    const urlOption = document.getElementById('camera-url-option');
    const entityOption = document.getElementById('camera-entity-option');
    const urlSection = document.getElementById('camera-url-section');
    const entitySection = document.getElementById('camera-entity-section');

    if (urlOption && entityOption && urlSection && entitySection) {
        urlOption.addEventListener('change', function() {
            if (this.checked) {
                urlSection.style.display = 'block';
                entitySection.style.display = 'none';
            }
        });

        entityOption.addEventListener('change', function() {
            if (this.checked) {
                urlSection.style.display = 'none';
                entitySection.style.display = 'block';
            }
        });
    }
}

async function loadCurrentSettings() {
    try {
        const response = await fetch(API.settings);
        if (response.ok) {
            const settings = await response.json();

            const cameraUrl = document.getElementById('camera-url');
            const haAccessToken = document.getElementById('ha-access-token');
            const urlOption = document.getElementById('camera-url-option');
            const entityOption = document.getElementById('camera-entity-option');
            const urlSection = document.getElementById('camera-url-section');
            const entitySection = document.getElementById('camera-entity-section');

            if (cameraUrl && settings.camera_url) {
                cameraUrl.value = settings.camera_url;
            }

            if (haAccessToken && settings.ha_access_token) {
                haAccessToken.value = settings.ha_access_token;
            }

            if (settings.camera_entity) {
                if (entityOption) entityOption.checked = true;
                if (urlOption) urlOption.checked = false;
                if (urlSection) urlSection.style.display = 'none';
                if (entitySection) entitySection.style.display = 'block';

                const cameraSelect = document.getElementById('camera-entity');
                if (cameraSelect) {
                    cameraSelect.setAttribute('data-current-value', settings.camera_entity);
                }
            } else if (settings.camera_url) {
                if (urlOption) urlOption.checked = true;
                if (entityOption) entityOption.checked = false;
                if (urlSection) urlSection.style.display = 'block';
                if (entitySection) entitySection.style.display = 'none';
            }

            return settings;
        }
    } catch (error) {
        console.error('Error loading current settings:', error);
    }
    return null;
}

/**
 * Generic dropdown loader. Fetches items from apiUrl and populates <select id=selectId>.
 * getItems(data) extracts the array from the response; toOption(item) maps each item to
 * { value, label }. Restores data-current-value when present.
 */
async function loadDropdownOptions(selectId, apiUrl, getItems, toOption, emptyMsg, errorMsg) {
    const select = document.getElementById(selectId);
    if (!select) return;

    try {
        const response = await fetch(apiUrl);
        if (response.ok) {
            const items = getItems(await response.json());

            if (items.length === 0) {
                select.innerHTML = `<option value="">${emptyMsg}</option>`;
            } else {
                select.innerHTML = `<option value="">Select…</option>`;
                items.forEach(item => {
                    const { value, label } = toOption(item);
                    const option = document.createElement('option');
                    option.value = value;
                    option.textContent = label;
                    select.appendChild(option);
                });

                const current = select.getAttribute('data-current-value');
                if (current) {
                    select.value = current;
                }
            }
        } else {
            select.innerHTML = `<option value="">${errorMsg}</option>`;
        }
    } catch {
        select.innerHTML = `<option value="">${errorMsg}</option>`;
    }
}

/** Runs async fn with button disabled and loading HTML, restores originalHtml when done. */
async function withButtonLoading(button, loadingHtml, originalHtml, fn) {
    button.disabled = true;
    button.innerHTML = loadingHtml;
    try {
        await fn();
    } finally {
        button.disabled = false;
        button.innerHTML = originalHtml;
    }
}

/** Extracts a displayable error message from a fetch error or JSON error response. */
function getErrorMessage(error) {
    if (error && typeof error === 'object' && error.detail) return error.detail;
    if (error instanceof Error) return error.message;
    return 'Unknown error';
}

async function testCamera() {
    const button = event.target;
    const urlOption = document.getElementById('camera-url-option');
    const entityOption = document.getElementById('camera-entity-option');

    let cameraSource, cameraValue;
    if (urlOption && urlOption.checked) {
        cameraSource = 'url';
        cameraValue = document.getElementById('camera-url').value;
    } else if (entityOption && entityOption.checked) {
        cameraSource = 'entity';
        cameraValue = document.getElementById('camera-entity').value;
    }

    if (!cameraValue) {
        showStatus('Please enter a camera URL or select an entity', 'error');
        return;
    }

    await withButtonLoading(
        button,
        '<i class="bi bi-arrow-clockwise"></i> Testing...',
        '<i class="bi bi-play-circle"></i> Test Camera Connection',
        async () => {
            try {
                const response = await fetch(API.cameraTest, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ source: cameraSource, value: cameraValue })
                });

                const result = await response.json();

                if (response.ok && result.success) {
                    showStatus('Camera connection successful!', 'success');
                } else {
                    showStatus('Camera connection failed: ' + getErrorMessage(result), 'error');
                }
            } catch (error) {
                showStatus('Network error during test', 'error');
            }
        }
    );
}

async function saveSettings() {
    const button = event.target;
    const urlOption = document.getElementById('camera-url-option');
    const entityOption = document.getElementById('camera-entity-option');
    const haAccessToken = document.getElementById('ha-access-token');

    const settingsData = {};

    if (haAccessToken && haAccessToken.value) {
        settingsData.ha_access_token = haAccessToken.value;
    }

    if (urlOption && urlOption.checked) {
        settingsData.camera_url = document.getElementById('camera-url').value;
        settingsData.camera_entity = null;
    } else if (entityOption && entityOption.checked) {
        settingsData.camera_entity = document.getElementById('camera-entity').value;
        settingsData.camera_url = null;
    }

    const weatherEntity = document.getElementById('weather-entity');
    if (weatherEntity && weatherEntity.value) {
        settingsData.weather_entity = weatherEntity.value;
    }

    await withButtonLoading(
        button,
        '<i class="bi bi-arrow-clockwise"></i> Saving...',
        '<i class="bi bi-check-circle"></i> Save Settings',
        async () => {
            try {
                const response = await fetch(API.settings, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settingsData)
                });

                if (response.ok) {
                    showNotification('Settings saved successfully!', 'success');
                    updateCameraStatus();
                } else {
                    const error = await response.json();
                    showNotification('Error saving settings: ' + getErrorMessage(error), 'error');
                }
            } catch (error) {
                showNotification('Network error while saving', 'error');
            }
        }
    );
}

function showStatus(message, type) {
    const statusSpan = document.getElementById('camera-status');
    if (statusSpan) {
        statusSpan.className = `ms-2 ${type === 'success' ? 'text-success' : 'text-danger'}`;
        statusSpan.textContent = message;
        setTimeout(() => {
            statusSpan.textContent = '';
            statusSpan.className = 'ms-2';
        }, 5000);
    }
}

async function refreshCameraEntities() {
    const button = event.target;
    await withButtonLoading(
        button,
        '<i class="bi bi-arrow-clockwise"></i> Refreshing...',
        '<i class="bi bi-arrow-clockwise"></i> Refresh Camera Entities',
        async () => {
            try {
                await loadDropdownOptions(
                    'camera-entity',
                    API.cameras,
                    data => data.cameras || [],
                    c => ({ value: c.entity_id, label: c.friendly_name }),
                    'No cameras found',
                    'Error loading cameras'
                );
                showNotification('Camera entities refreshed successfully!', 'success');
            } catch (error) {
                showNotification('Error refreshing camera entities', 'error');
            }
        }
    );
}

function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type === 'success' ? 'success' : 'danger'} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 1050; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(notification);
    setTimeout(() => {
        if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
        }
    }, 5000);
}

async function updateCameraStatus() {
    const statusElement = document.getElementById('camera-connection-status');
    if (!statusElement) return;

    try {
        const response = await fetch(API.settings);
        if (response.ok) {
            const settings = await response.json();
            if (settings.camera_entity) {
                statusElement.textContent = 'Connected (HA Entity)';
                statusElement.className = 'badge bg-success';
            } else if (settings.camera_url) {
                statusElement.textContent = 'Connected (URL)';
                statusElement.className = 'badge bg-success';
            } else {
                statusElement.textContent = 'Not Configured';
                statusElement.className = 'badge bg-warning';
            }
        } else {
            statusElement.textContent = 'Error';
            statusElement.className = 'badge bg-danger';
        }
    } catch (error) {
        statusElement.textContent = 'Unknown';
        statusElement.className = 'badge bg-secondary';
    }
}

async function saveWeatherSettings() {
    const button = event.target;
    const weatherEntity = document.getElementById('weather-entity');

    if (!weatherEntity) {
        showNotification('Weather entity field not found', 'error');
        return;
    }

    await withButtonLoading(
        button,
        '<i class="bi bi-arrow-clockwise"></i> Saving...',
        '<i class="bi bi-save"></i> Save Weather Settings',
        async () => {
            try {
                const response = await fetch(API.settings, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ weather_entity: weatherEntity.value || null })
                });

                if (response.ok) {
                    showNotification('Weather settings saved successfully!', 'success');
                } else {
                    const error = await response.json();
                    showNotification('Error saving weather settings: ' + getErrorMessage(error), 'error');
                }
            } catch (error) {
                showNotification('Network error while saving weather settings', 'error');
            }
        }
    );
}

async function loadNotifyServices() {
    const container = document.getElementById('notify-services-list');
    if (!container) return;
    container.innerHTML = '<span class="text-muted small">Loading\u2026</span>';
    try {
        const resp = await fetch(API.notifyServices);
        const data = await resp.json();
        const services = data.services || [];
        if (services.length === 0) {
            container.innerHTML = '<span class="text-muted small">No notify services found.</span>';
            return;
        }
        const currentSelected = (window._currentNotifyServices || []);
        container.innerHTML = services.map(s => {
            const suffix = s.name.replace('notify.', '');
            const badge = s.classification === 'image'
                ? '<span class="badge bg-primary ms-1" title="Image capable">\uD83D\uDCF1 Mobile</span>'
                : s.classification === 'audio'
                ? '<span class="badge bg-secondary ms-1" title="Audio only">\uD83D\uDD0A Audio</span>'
                : '<span class="badge bg-info ms-1" title="Full payload">\uD83D\uDCE1 Other</span>';
            const checked = currentSelected.includes(s.name) ? 'checked' : '';
            return `<div class="form-check">
                <input class="form-check-input notify-service-check" type="checkbox"
                    value="${s.name}" id="ns-${suffix}" ${checked}>
                <label class="form-check-label" for="ns-${suffix}">
                    ${suffix} ${badge}
                </label>
            </div>`;
        }).join('');
    } catch (e) {
        container.innerHTML = '<span class="text-danger small">Error loading services.</span>';
    }
}

async function loadLlmvisionProviders() {
    loadDropdownOptions(
        'llmvision-provider',
        API.llmvisionProviders,
        data => data.providers || [],
        p => ({ value: p.id, label: p.title }),
        'No llmvision providers found',
        'Error loading providers'
    );
}

function checkAiPublicPathWarning() {
    const enabled = document.getElementById('llmvision-enabled');
    const pathInput = document.getElementById('public-image-path');
    const warning = document.getElementById('ai-public-path-warning');
    if (!enabled || !warning) return;
    const needsWarning = enabled.checked && !(pathInput && pathInput.value.trim());
    warning.style.display = needsWarning ? '' : 'none';
}

async function saveAiDescription() {
    try {
        const payload = {
            llmvision_enabled: document.getElementById('llmvision-enabled').checked,
            llmvision_provider: document.getElementById('llmvision-provider').value.trim() || null,
            llmvision_model: document.getElementById('llmvision-model').value.trim(),
            llmvision_prompt: document.getElementById('llmvision-prompt').value,
            llmvision_max_tokens: parseInt(document.getElementById('llmvision-max-tokens').value),
            default_message: document.getElementById('default-message').value.trim(),
        };
        const resp = await fetch(API.settings, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (resp.ok) {
            alert('AI description settings saved!');
            checkAiPublicPathWarning();
        } else {
            const err = await resp.json();
            alert('Error: ' + (err.detail || 'Unknown error'));
        }
    } catch (e) {
        alert('Error saving AI settings: ' + e.message);
    }
}

async function saveNotifications() {
    try {
        const checks = document.querySelectorAll('.notify-service-check:checked');
        const selectedServices = Array.from(checks).map(c => c.value);
        window._currentNotifyServices = selectedServices;
        const webhookUrl = document.getElementById('webhook-url').value.trim();
        const resp = await fetch(API.settings, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ha_notify_services: selectedServices,
                notification_webhook: webhookUrl || null,
            }),
        });
        if (resp.ok) {
            alert('Notification settings saved!');
        } else {
            const err = await resp.json();
            alert('Error: ' + (err.detail || 'Unknown error'));
        }
    } catch (e) {
        alert('Error saving notification settings: ' + e.message);
    }
}

async function savePublicImagePath() {
    try {
        const path = document.getElementById('public-image-path').value.trim();
        const resp = await fetch(API.settings, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ public_image_path: path || null }),
        });
        if (resp.ok) {
            alert('Public image path saved!');
            checkAiPublicPathWarning();
        } else {
            const err = await resp.json();
            alert('Error: ' + (err.detail || 'Unknown error'));
        }
    } catch (e) {
        alert('Error saving public image path: ' + e.message);
    }
}

async function saveTriggerEntity() {
    try {
        const entity = document.getElementById('trigger-entity').value;
        const resp = await fetch(API.settings, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ trigger_entity: entity || null }),
        });
        if (resp.ok) { alert('Trigger entity saved!'); }
        else { const err = await resp.json(); alert('Error: ' + (err.detail || 'Unknown')); }
    } catch (e) { alert('Error: ' + e.message); }
}

function loadBinarySensors() {
    loadDropdownOptions(
        'trigger-entity',
        API.binarySensors,
        data => data.entities || [],
        e => ({ value: e.entity_id, label: e.friendly_name }),
        'No binary sensors found',
        'Error loading sensors'
    );
}

function copyAutomationYaml() {
    const entity = document.getElementById('trigger-entity').value;
    if (!entity) { alert('Select a binary sensor first.'); return; }
    const yaml = `# Add to configuration.yaml:
rest_command:
  doorbell_ring:
    url: "http://localhost:8099/api/doorbell/ring"
    method: POST

# Automation:
alias: Doorbell ring
triggers:
  - trigger: state
    entity_id: ${entity}
    from: "off"
    to: "on"
actions:
  - action: rest_command.doorbell_ring`;
    navigator.clipboard.writeText(yaml)
        .then(() => alert('Automation YAML copied to clipboard!'))
        .catch(() => { alert('Copy failed. YAML:\n\n' + yaml); });
}

// Export functions for global access
window.testCamera = testCamera;
window.saveSettings = saveSettings;
window.refreshCameraEntities = refreshCameraEntities;
window.updateCameraStatus = updateCameraStatus;
window.saveWeatherSettings = saveWeatherSettings;
