// Main JavaScript for Doorbell Face Recognition

// Global variables
let isCapturing = false;
let currentModal = null;

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Setup event listeners
    setupEventListeners();
    
    // Initialize tooltips
    initializeTooltips();
    
    // Setup auto-refresh for dashboard
    if (window.location.pathname === '/') {
        setupAutoRefresh();
    }
    
    // Setup drag and drop for file uploads
    setupDragAndDrop();
}

function setupEventListeners() {
    // Global capture button
    const captureButtons = document.querySelectorAll('[onclick="captureFrame()"]');
    captureButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            captureFrame();
        });
    });
    
    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + Space for capture
        if ((e.ctrlKey || e.metaKey) && e.code === 'Space') {
            e.preventDefault();
            captureFrame();
        }
        
        // Escape to close modals
        if (e.key === 'Escape') {
            closeCurrentModal();
        }
    });
}

function initializeTooltips() {
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

function setupAutoRefresh() {
    // Auto-refresh dashboard every 30 seconds
    setInterval(function() {
        if (document.visibilityState === 'visible') {
            refreshDashboardData();
        }
    }, 30000);
}

function setupDragAndDrop() {
    // Setup drag and drop for file inputs
    const fileInputs = document.querySelectorAll('input[type="file"]');
    
    fileInputs.forEach(input => {
        const container = input.closest('.modal-body') || input.parentElement;
        
        container.addEventListener('dragover', function(e) {
            e.preventDefault();
            container.classList.add('dragover');
        });
        
        container.addEventListener('dragleave', function(e) {
            e.preventDefault();
            container.classList.remove('dragover');
        });
        
        container.addEventListener('drop', function(e) {
            e.preventDefault();
            container.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0 && files[0].type.startsWith('image/')) {
                input.files = files;
                
                // Trigger change event
                const event = new Event('change', { bubbles: true });
                input.dispatchEvent(event);
            }
        });
    });
}

// Camera capture function
async function captureFrame() {
    if (isCapturing) return;
    
    isCapturing = true;
    const originalText = 'Capture';
    
    // Update all capture buttons
    const captureButtons = document.querySelectorAll('[onclick="captureFrame()"]');
    captureButtons.forEach(btn => {
        btn.disabled = true;
        btn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Capturing...';
    });
    
    try {
        const response = await fetch('/api/camera/capture', {
            method: 'POST'
        });
        
        if (response.ok) {
            const result = await response.json();
            
            // Show success notification
            showNotification('Frame captured successfully!', 'success');
            
            // If faces were detected, show details
            if (result.results && result.results.faces_detected > 0) {
                showNotification(
                    `Detected ${result.results.faces_detected} face(s)`, 
                    'info'
                );
            }
            
            // Refresh page after a short delay
            setTimeout(() => {
                location.reload();
            }, 1500);
            
        } else {
            const error = await response.json();
            showNotification('Error capturing frame: ' + error.detail, 'error');
        }
        
    } catch (error) {
        console.error('Capture error:', error);
        showNotification('Network error during capture', 'error');
    } finally {
        isCapturing = false;
        
        // Restore button states
        captureButtons.forEach(btn => {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-camera"></i> ' + originalText;
        });
    }
}

// Notification system
function showNotification(message, type = 'info', duration = 3000) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${getBootstrapAlertClass(type)} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Auto-remove after duration
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, duration);
}

function getBootstrapAlertClass(type) {
    const typeMap = {
        'success': 'success',
        'error': 'danger',
        'warning': 'warning',
        'info': 'info'
    };
    return typeMap[type] || 'info';
}

// Dashboard data refresh
async function refreshDashboardData() {
    try {
        // Refresh statistics
        const statsResponse = await fetch('/api/stats');
        if (statsResponse.ok) {
            const stats = await statsResponse.json();
            updateDashboardStats(stats);
        }
        
        // Refresh recent events (only update counts, not full reload)
        const eventsResponse = await fetch('/api/events?limit=10');
        if (eventsResponse.ok) {
            const events = await eventsResponse.json();
            updateEventCounts(events.events);
        }
        
    } catch (error) {
        console.error('Error refreshing dashboard:', error);
    }
}

function updateDashboardStats(stats) {
    // Update stat cards if they exist
    const totalEventsEl = document.getElementById('total-events');
    const knownFacesEl = document.getElementById('known-faces');
    const unknownFacesEl = document.getElementById('unknown-faces');
    const totalPersonsEl = document.getElementById('total-persons');
    
    if (totalEventsEl) totalEventsEl.textContent = stats.total_events;
    if (knownFacesEl) knownFacesEl.textContent = stats.known_events;
    if (unknownFacesEl) unknownFacesEl.textContent = stats.unknown_events;
    if (totalPersonsEl) totalPersonsEl.textContent = stats.total_persons;
}

function updateEventCounts(events) {
    const knownCount = events.filter(e => e.is_known).length;
    const unknownCount = events.length - knownCount;
    
    const knownEl = document.getElementById('known-faces');
    const unknownEl = document.getElementById('unknown-faces');
    
    if (knownEl) knownEl.textContent = knownCount;
    if (unknownEl) unknownEl.textContent = unknownCount;
}

// Modal management
function closeCurrentModal() {
    const openModals = document.querySelectorAll('.modal.show');
    openModals.forEach(modal => {
        const modalInstance = bootstrap.Modal.getInstance(modal);
        if (modalInstance) {
            modalInstance.hide();
        }
    });
}

// Image loading with error handling
function handleImageError(img) {
    img.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGVlMmU2Ii8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzZjNzU3ZCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPkltYWdlIG5vdCBmb3VuZDwvdGV4dD48L3N2Zz4=';
    img.alt = 'Image not found';
    img.classList.add('opacity-50');
}

// Add error handling to all images
document.addEventListener('DOMContentLoaded', function() {
    const images = document.querySelectorAll('img[src*="/api/images/"]');
    images.forEach(img => {
        img.addEventListener('error', function() {
            handleImageError(this);
        });
    });
});

// Form validation helpers
function validateForm(formElement) {
    const requiredFields = formElement.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// File size validation
function validateFileSize(file, maxSizeMB = 10) {
    const maxSizeBytes = maxSizeMB * 1024 * 1024;
    return file.size <= maxSizeBytes;
}

// Image file validation
function validateImageFile(file) {
    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
    return allowedTypes.includes(file.type);
}

// Loading state management
function setLoadingState(element, isLoading, originalText = '') {
    if (isLoading) {
        element.disabled = true;
        element.dataset.originalText = element.innerHTML;
        element.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';
    } else {
        element.disabled = false;
        element.innerHTML = element.dataset.originalText || originalText;
    }
}

// Debounce function for search inputs
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Format date for display
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

// Format confidence percentage
function formatConfidence(confidence) {
    return Math.round(confidence * 100) + '%';
}

// Copy to clipboard
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showNotification('Copied to clipboard!', 'success', 1500);
    } catch (error) {
        console.error('Failed to copy:', error);
        showNotification('Failed to copy to clipboard', 'error');
    }
}

// Download file
function downloadFile(url, filename) {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Local storage helpers
function saveToLocalStorage(key, data) {
    try {
        localStorage.setItem(key, JSON.stringify(data));
    } catch (error) {
        console.error('Failed to save to localStorage:', error);
    }
}

function loadFromLocalStorage(key, defaultValue = null) {
    try {
        const data = localStorage.getItem(key);
        return data ? JSON.parse(data) : defaultValue;
    } catch (error) {
        console.error('Failed to load from localStorage:', error);
        return defaultValue;
    }
}

// Theme management
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-bs-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-bs-theme', newTheme);
    saveToLocalStorage('theme', newTheme);
}

// Initialize theme from localStorage
document.addEventListener('DOMContentLoaded', function() {
    const savedTheme = loadFromLocalStorage('theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-bs-theme', savedTheme);
    }
});

// Export functions for global access
window.captureFrame = captureFrame;
window.showNotification = showNotification;
window.handleImageError = handleImageError;
window.validateForm = validateForm;
window.setLoadingState = setLoadingState;
window.formatDate = formatDate;
window.formatConfidence = formatConfidence;
window.copyToClipboard = copyToClipboard;
window.downloadFile = downloadFile;
window.toggleTheme = toggleTheme;
