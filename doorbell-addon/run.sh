#!/usr/bin/with-contenv bashio
# ==============================================================================
# Home Assistant Community Add-on: Doorbell Face Recognition
# Runs the Doorbell Face Recognition service
# ==============================================================================

# Wait for Home Assistant to be available
bashio::log.info "Starting Doorbell Face Recognition addon..."

# Get configuration
CAMERA_URL=$(bashio::config 'camera_url')
STORAGE_PATH=$(bashio::config 'storage_path')
RETENTION_DAYS=$(bashio::config 'retention_days')
FACE_CONFIDENCE=$(bashio::config 'face_confidence_threshold')
NOTIFICATION_WEBHOOK=$(bashio::config 'notification_webhook')
DATABASE_ENCRYPTION=$(bashio::config 'database_encryption')

# Export environment variables
export CAMERA_URL
export STORAGE_PATH
export RETENTION_DAYS
export FACE_CONFIDENCE_THRESHOLD=$FACE_CONFIDENCE
export NOTIFICATION_WEBHOOK
export DATABASE_ENCRYPTION
export HASSIO_TOKEN
export SUPERVISOR_TOKEN

# Create storage directories
mkdir -p "${STORAGE_PATH}/images"
mkdir -p "${STORAGE_PATH}/faces"
mkdir -p "${STORAGE_PATH}/database"

# Set permissions
chown -R root:root "${STORAGE_PATH}"
chmod -R 755 "${STORAGE_PATH}"

bashio::log.info "Configuration loaded:"
bashio::log.info "Camera URL: ${CAMERA_URL}"
bashio::log.info "Storage Path: ${STORAGE_PATH}"
bashio::log.info "Retention Days: ${RETENTION_DAYS}"
bashio::log.info "Face Confidence: ${FACE_CONFIDENCE}"

# Start the application
cd /app
exec python3 -m uvicorn src.app:app --host 0.0.0.0 --port 8099 --log-level info
