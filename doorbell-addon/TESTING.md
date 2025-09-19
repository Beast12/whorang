# Testing Your Private Doorbell Addon in Home Assistant

## 🚀 Quick Start - Local Installation

### Option 1: Automated Installation Script
```bash
cd /home/koen/Github/whorang/doorbell-addon
sudo ./install-local.sh
```

### Option 2: Manual Installation

1. **Copy addon to Home Assistant:**
```bash
# Find your HA addons directory (one of these):
sudo mkdir -p /usr/share/hassio/addons/local
sudo mkdir -p /data/addons/local  
sudo mkdir -p /config/addons/local

# Copy the addon
sudo cp -r /home/koen/Github/whorang/doorbell-addon /usr/share/hassio/addons/local/doorbell-face-recognition
```

2. **Restart Home Assistant Supervisor:**
```bash
sudo systemctl restart hassio-supervisor
```

3. **Install via UI:**
   - Go to **Settings → Add-ons → Local add-ons**
   - Find "Doorbell Face Recognition"
   - Click **Install**

## 🔧 Configuration

### Required Settings
```yaml
camera_url: "rtsp://your-camera-ip:554/stream"  # Your actual camera
storage_path: "/share/doorbell"                 # Default is fine
retention_days: 30                              # Adjust as needed
face_confidence_threshold: 0.6                  # 0.6 recommended
```

### Optional Settings
```yaml
notification_webhook: "http://your-webhook-url"  # For notifications
database_encryption: false                      # Enable for security
```

## 📱 Testing Face Recognition

### 1. Access Web Interface
- URL: `http://your-ha-ip:8099`
- Available immediately after addon starts

### 2. Add Known Faces
1. Go to **Dashboard** → **Manage People**
2. Click **Add Person**
3. Upload clear face photos
4. System will extract and store face encodings

### 3. Test Camera Integration
1. Configure your camera URL in addon settings
2. Use **Manual Capture** to test camera connection
3. Check **Gallery** for captured images

### 4. Monitor Home Assistant Integration
Check these entities in HA:
- `sensor.doorbell_last_event`
- `sensor.doorbell_known_faces_today`
- `sensor.doorbell_unknown_faces_today`
- `sensor.doorbell_total_events`

## 🐛 Troubleshooting

### Addon Not Appearing
```bash
# Check addon directory exists
ls -la /usr/share/hassio/addons/local/doorbell-face-recognition

# Restart supervisor
sudo systemctl restart hassio-supervisor

# Check supervisor logs
sudo journalctl -u hassio-supervisor -f
```

### Face Recognition Not Working
1. Check addon logs for "Face recognition capabilities loaded successfully"
2. Verify camera URL is accessible from HA
3. Test manual capture first

### Camera Connection Issues
- Ensure camera URL is correct and accessible
- Try different stream formats (RTSP/HTTP)
- Check network connectivity from HA to camera

## 🔍 Logs and Debugging

### View Addon Logs
- Home Assistant → Settings → Add-ons → Doorbell Face Recognition → Log

### Enable Debug Mode
Add to addon configuration:
```yaml
debug: true
```

### Check Face Recognition Status
The addon logs will show:
- "Face recognition capabilities loaded successfully" ✅
- "Loaded X known face encodings" 
- Camera connection status
- Face detection results

## 📊 Expected Behavior

### Successful Startup
```
Face recognition capabilities loaded2025-09-19 15:42:45 [info     ] Starting Doorbell Face Recognition addon version=1.0.52...
Directory ensured path=/share/doorbell
Loaded X known face encodings
```

### Face Detection
```
Face detected with confidence 0.85
Known person: John Doe (confidence: 0.92)
Event saved to database
Home Assistant sensor updated
```

## 🚀 Next Steps After Testing

1. **Add more face samples** for better recognition accuracy
2. **Configure notifications** via webhook or HA automations  
3. **Set up automations** based on face detection events
4. **Adjust confidence threshold** based on your results
5. **Monitor storage usage** and adjust retention settings

## 🔒 Production Deployment

Once testing is complete, you can:
1. **Publish to GitHub** (make repo public)
2. **Set up GitHub Actions** for automated builds
3. **Publish to Home Assistant Community Add-ons**
4. **Create HACS integration** for easy updates

Your addon is now production-ready with full AI-powered face recognition!
