#!/bin/bash

# Local Home Assistant Addon Installation Script
# This script installs the doorbell addon for local development/testing

set -e

echo "🏠 Installing Doorbell Face Recognition Addon Locally"

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root or with sudo"
    exit 1
fi

# Define paths
ADDON_NAME="doorbell-face-recognition"
SOURCE_DIR="$(dirname "$(readlink -f "$0")")"
HA_ADDONS_DIR="/usr/share/hassio/addons/local"
TARGET_DIR="$HA_ADDONS_DIR/$ADDON_NAME"

# Alternative paths for different HA installations
ALTERNATIVE_PATHS=(
    "/usr/share/hassio/addons/local"
    "/data/addons/local" 
    "/config/addons/local"
    "$HOME/homeassistant/addons/local"
)

# Find Home Assistant addons directory
echo "🔍 Looking for Home Assistant addons directory..."
FOUND_PATH=""
for path in "${ALTERNATIVE_PATHS[@]}"; do
    if [ -d "$(dirname "$path")" ]; then
        echo "   Checking: $path"
        mkdir -p "$path" 2>/dev/null || true
        if [ -w "$path" ] || [ -w "$(dirname "$path")" ]; then
            FOUND_PATH="$path"
            echo "   ✅ Found writable path: $path"
            break
        fi
    fi
done

if [ -z "$FOUND_PATH" ]; then
    echo "❌ Could not find Home Assistant addons directory"
    echo "   Please manually copy the addon to your HA addons/local directory"
    echo "   Common locations:"
    for path in "${ALTERNATIVE_PATHS[@]}"; do
        echo "   - $path"
    done
    exit 1
fi

HA_ADDONS_DIR="$FOUND_PATH"
TARGET_DIR="$HA_ADDONS_DIR/$ADDON_NAME"

# Create target directory
echo "📁 Creating addon directory: $TARGET_DIR"
mkdir -p "$TARGET_DIR"

# Copy addon files
echo "📋 Copying addon files..."
cp -r "$SOURCE_DIR"/* "$TARGET_DIR/"

# Set proper permissions
echo "🔐 Setting permissions..."
chown -R root:root "$TARGET_DIR"
chmod -R 755 "$TARGET_DIR"
chmod +x "$TARGET_DIR/run.sh" 2>/dev/null || true

# Create data directories
echo "📂 Creating data directories..."
mkdir -p /share/doorbell/{images,faces,database}
chown -R root:root /share/doorbell 2>/dev/null || true

echo "✅ Installation complete!"
echo ""
echo "📋 Next steps:"
echo "1. Restart Home Assistant Supervisor:"
echo "   sudo systemctl restart hassio-supervisor"
echo ""
echo "2. Go to Home Assistant > Settings > Add-ons > Local add-ons"
echo "3. You should see 'Doorbell Face Recognition' addon"
echo "4. Click on it and install"
echo ""
echo "🔧 Configuration:"
echo "- Update camera_url to your actual camera stream"
echo "- Adjust face_confidence_threshold (0.6 is recommended)"
echo "- Set notification_webhook if desired"
echo ""
echo "🌐 Web interface will be available at:"
echo "   http://your-ha-ip:8099"
