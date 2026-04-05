#!/usr/bin/with-contenv bashio
# ==============================================================================
# Home Assistant Community Add-on: WhoRang Doorbell
# Runs the WhoRang doorbell service
# ==============================================================================

bashio::log.info "Starting WhoRang doorbell addon..."

# Get configuration
CAMERA_URL=$(bashio::config 'camera_url')
STORAGE_PATH=$(bashio::config 'storage_path')
RETENTION_DAYS=$(bashio::config 'retention_days')
NOTIFICATION_WEBHOOK=$(bashio::config 'notification_webhook')

# Export environment variables
export CAMERA_URL
export STORAGE_PATH
export RETENTION_DAYS
export NOTIFICATION_WEBHOOK
export HASSIO_TOKEN
export SUPERVISOR_TOKEN

# Handle optional camera_entity
if bashio::config.exists 'camera_entity' && ! bashio::config.is_empty 'camera_entity'; then
    export CAMERA_ENTITY=$(bashio::config 'camera_entity')
fi

# Handle optional ha_access_token
if bashio::config.exists 'ha_access_token' && ! bashio::config.is_empty 'ha_access_token'; then
    export HA_ACCESS_TOKEN=$(bashio::config 'ha_access_token')
fi

# Handle optional face recognition settings
if bashio::config.exists 'face_recognition_enabled'; then
    export FACE_RECOGNITION_ENABLED=$(bashio::config 'face_recognition_enabled')
fi
if bashio::config.exists 'face_recognition_model' && ! bashio::config.is_empty 'face_recognition_model'; then
    export FACE_RECOGNITION_MODEL=$(bashio::config 'face_recognition_model')
fi
export INSIGHTFACE_HOME="${STORAGE_PATH}/insightface_models"
mkdir -p "${STORAGE_PATH}/persons"
mkdir -p "${STORAGE_PATH}/insightface_models"

# Create storage directories
mkdir -p "${STORAGE_PATH}/images"
mkdir -p "${STORAGE_PATH}/database"
mkdir -p "${STORAGE_PATH}/config"

# Set permissions
chown -R root:root "${STORAGE_PATH}"
chmod -R 755 "${STORAGE_PATH}"

bashio::log.info "Configuration loaded:"
bashio::log.info "Camera URL: ${CAMERA_URL}"
bashio::log.info "Storage Path: ${STORAGE_PATH}"
bashio::log.info "Retention Days: ${RETENTION_DAYS}"

# Start the application
cd /app
exec python3 -m uvicorn src.app:app --host 0.0.0.0 --port 8099 --log-level info
