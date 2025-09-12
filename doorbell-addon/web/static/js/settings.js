// Settings page JavaScript functionality

document.addEventListener('DOMContentLoaded', function() {
    initializeSettings();
});

function initializeSettings() {
    // Setup camera source radio buttons
    setupCameraSourceToggle();
    
    // Load current settings first, then load cameras
    loadCurrentSettings().then(() => {
        // Load available cameras after settings are loaded
        loadAvailableCameras();
    });
    
    // Setup confidence threshold slider
    setupConfidenceSlider();
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
        const response = await fetch('api/settings');
        if (response.ok) {
            const settings = await response.json();
            
            // Update form fields with current settings
            const cameraUrl = document.getElementById('camera-url');
            const haAccessToken = document.getElementById('ha-access-token');
            const confidenceSlider = document.getElementById('confidence-threshold');
            const confidenceValue = document.getElementById('confidence-value');
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
            
            if (confidenceSlider && settings.face_confidence_threshold !== undefined) {
                confidenceSlider.value = settings.face_confidence_threshold;
                if (confidenceValue) {
                    confidenceValue.textContent = Math.round(settings.face_confidence_threshold * 100) + '%';
                }
            }
            
            // Set camera source based on settings
            if (settings.camera_entity) {
                if (entityOption) entityOption.checked = true;
                if (urlOption) urlOption.checked = false;
                if (urlSection) urlSection.style.display = 'none';
                if (entitySection) entitySection.style.display = 'block';
                
                // Store current entity for later restoration
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
        }
    } catch (error) {
        console.error('Error loading current settings:', error);
    }
}

async function loadAvailableCameras() {
    const cameraSelect = document.getElementById('camera-entity');
    if (!cameraSelect) return;
    
    try {
        const response = await fetch('api/cameras');
        if (response.ok) {
            const data = await response.json();
            const cameras = data.cameras || [];
            
            // Clear existing options
            cameraSelect.innerHTML = '';
            
            if (cameras.length === 0) {
                cameraSelect.innerHTML = '<option value="">No cameras found</option>';
            } else {
                cameraSelect.innerHTML = '<option value="">Select a camera...</option>';
                cameras.forEach(camera => {
                    const option = document.createElement('option');
                    option.value = camera.entity_id;
                    option.textContent = camera.friendly_name;
                    cameraSelect.appendChild(option);
                });
                
                // Set the selected value from current settings
                const currentEntity = cameraSelect.getAttribute('data-current-value');
                if (currentEntity) {
                    cameraSelect.value = currentEntity;
                }
            }
        } else {
            cameraSelect.innerHTML = '<option value="">Error loading cameras</option>';
        }
    } catch (error) {
        console.error('Error loading cameras:', error);
        cameraSelect.innerHTML = '<option value="">Error loading cameras</option>';
    }
}

function setupConfidenceSlider() {
    const slider = document.getElementById('confidence-threshold');
    const valueDisplay = document.getElementById('confidence-value');
    
    if (slider && valueDisplay) {
        slider.addEventListener('input', function() {
            updateConfidenceValue(this.value);
        });
    }
}

function updateConfidenceValue(value) {
    const valueDisplay = document.getElementById('confidence-value');
    if (valueDisplay) {
        valueDisplay.textContent = value + '%';
    }
}

async function testCamera() {
    const button = event.target;
    const statusSpan = document.getElementById('camera-status');
    const urlOption = document.getElementById('camera-url-option');
    const entityOption = document.getElementById('camera-entity-option');
    
    // Determine which camera source is selected
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
    
    // Update button state
    button.disabled = true;
    button.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Testing...';
    
    try {
        const response = await fetch('api/camera/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                source: cameraSource,
                value: cameraValue
            })
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            showStatus('Camera connection successful!', 'success');
        } else {
            showStatus('Camera connection failed: ' + (result.error || 'Unknown error'), 'error');
        }
        
    } catch (error) {
        console.error('Test camera error:', error);
        showStatus('Network error during test', 'error');
    } finally {
        // Restore button state
        button.disabled = false;
        button.innerHTML = '<i class="bi bi-play-circle"></i> Test Camera Connection';
    }
}

async function saveSettings() {
    const button = event.target;
    const urlOption = document.getElementById('camera-url-option');
    const entityOption = document.getElementById('camera-entity-option');
    const confidenceSlider = document.getElementById('confidence-threshold');
    const haAccessToken = document.getElementById('ha-access-token');
    
    // Collect settings data
    const settings = {
        confidence_threshold: confidenceSlider ? parseFloat(confidenceSlider.value) / 100 : 0.6
    };
    
    // Add Home Assistant access token
    if (haAccessToken && haAccessToken.value) {
        settings.ha_access_token = haAccessToken.value;
    }
    
    // Add camera configuration
    if (urlOption && urlOption.checked) {
        settings.camera_url = document.getElementById('camera-url').value;
        settings.camera_entity = null;
    } else if (entityOption && entityOption.checked) {
        settings.camera_entity = document.getElementById('camera-entity').value;
        settings.camera_url = null;
    }
    
    // Update button state
    button.disabled = true;
    button.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Saving...';
    
    try {
        const response = await fetch('api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });
        
        if (response.ok) {
            showNotification('Settings saved successfully!', 'success');
        } else {
            const error = await response.json();
            showNotification('Error saving settings: ' + error.detail, 'error');
        }
        
    } catch (error) {
        console.error('Save settings error:', error);
        showNotification('Network error while saving', 'error');
    } finally {
        // Restore button state
        button.disabled = false;
        button.innerHTML = '<i class="bi bi-check-circle"></i> Save Settings';
    }
}

function showStatus(message, type) {
    const statusSpan = document.getElementById('camera-status');
    if (statusSpan) {
        statusSpan.className = `ms-2 ${type === 'success' ? 'text-success' : 'text-danger'}`;
        statusSpan.textContent = message;
        
        // Clear after 5 seconds
        setTimeout(() => {
            statusSpan.textContent = '';
            statusSpan.className = 'ms-2';
        }, 5000);
    }
}

async function refreshCameraEntities() {
    const button = event.target;
    
    // Update button state
    button.disabled = true;
    button.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Refreshing...';
    
    try {
        await loadAvailableCameras();
        showNotification('Camera entities refreshed successfully!', 'success');
    } catch (error) {
        console.error('Refresh cameras error:', error);
        showNotification('Error refreshing camera entities', 'error');
    } finally {
        // Restore button state
        button.disabled = false;
        button.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Refresh Camera Entities';
    }
}

function showNotification(message, type) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type === 'success' ? 'success' : 'danger'} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 1050; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
        }
    }, 5000);
}

// Export functions for global access
window.testCamera = testCamera;
window.saveSettings = saveSettings;
window.updateConfidenceValue = updateConfidenceValue;
window.refreshCameraEntities = refreshCameraEntities;
