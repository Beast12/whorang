# Doorbell Face Recognition Add-on

[![Version](https://img.shields.io/badge/version-1.0.6-blue.svg)](https://github.com/Beast12/whorang/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Add--on-blue.svg)](https://www.home-assistant.io/)

AI-powered doorbell with face recognition capabilities for Home Assistant. This add-on provides real-time face detection and recognition, allowing you to identify known visitors and receive notifications when unknown faces are detected at your door.

## Features

- 🎯 **AI-Powered Face Recognition** - Uses the face_recognition library for accurate face detection and identification
- 📹 **Real-time Camera Monitoring** - Continuous monitoring of your doorbell camera feed
- 🏠 **Home Assistant Integration** - Native integration with sensors, notifications, and automations
- 🖥️ **Web Interface** - Beautiful, responsive web UI for managing faces and viewing events
- 🔒 **Privacy-Focused** - All processing happens locally, no cloud dependencies
- 📱 **Multi-Platform Support** - Works on amd64, arm64, armv7, and other architectures
- 🗄️ **Local Storage** - SQLite database with optional encryption
- 🔔 **Flexible Notifications** - Home Assistant notifications and webhook support
- 📊 **Event Gallery** - Browse and manage doorbell events with filtering
- ⚙️ **Configurable Settings** - Adjustable confidence thresholds and retention policies

## Screenshots

### Dashboard
![Dashboard](https://via.placeholder.com/800x400/0d6efd/ffffff?text=Dashboard+View)

### Gallery
![Gallery](https://via.placeholder.com/800x400/198754/ffffff?text=Event+Gallery)

### Settings
![Settings](https://via.placeholder.com/800x400/ffc107/000000?text=Settings+Page)

## Installation

### Method 1: Add Repository to Home Assistant

1. In Home Assistant, go to **Supervisor** → **Add-on Store**
2. Click the **⋮** menu in the top right corner
3. Select **Repositories**
4. Add this repository URL: `https://github.com/Beast12/whorang`
5. Find "Doorbell Face Recognition" in the add-on store
6. Click **Install**

### Method 2: Manual Installation

1. Clone this repository to your Home Assistant add-ons directory:
   ```bash
   cd /usr/share/hassio/addons/local/
   git clone https://github.com/Beast12/whorang.git
   cd whorang/doorbell-addon
   ```

2. Restart Home Assistant
3. Go to **Supervisor** → **Add-on Store** → **Local Add-ons**
4. Install "Doorbell Face Recognition"

## Configuration

### Basic Configuration

```yaml
camera_url: "rtsp://192.168.1.100:554/stream"
storage_path: "/share/doorbell"
retention_days: 30
face_confidence_threshold: 0.6
notification_webhook: ""
database_encryption: false
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `camera_url` | string | Required | RTSP or HTTP URL of your doorbell camera |
| `storage_path` | string | `/share/doorbell` | Path to store images and database |
| `retention_days` | integer | 30 | Days to keep events (1-365) |
| `face_confidence_threshold` | float | 0.6 | Confidence threshold for face recognition (0.1-1.0) |
| `notification_webhook` | string | "" | Optional webhook URL for external notifications |
| `database_encryption` | boolean | false | Enable database encryption for face data |

### Camera URL Examples

- **RTSP**: `rtsp://username:password@192.168.1.100:554/stream`
- **HTTP**: `http://192.168.1.100:8080/video`
- **ONVIF**: `rtsp://192.168.1.100:554/onvif1`
- **Generic**: `rtsp://192.168.1.100:554/live/ch00_0`

## Usage

### Initial Setup

1. **Configure Camera**: Set your doorbell camera URL in the add-on configuration
2. **Start Add-on**: Enable "Start on boot" and "Auto update" options
3. **Access Web Interface**: Open the add-on web UI (port 8099)
4. **Test Camera**: Use the "Capture" button to test camera connectivity

### Adding People

1. Go to the **Dashboard** or **Gallery**
2. Click **"Add Person"** and enter a name
3. Upload face images using **"Add Face"** button
4. The system will extract and store face encodings

### Labeling Unknown Faces

1. When unknown faces are detected, they appear in the gallery
2. Click **"Label"** on any unknown face event
3. Select an existing person or create a new one
4. The system learns from this labeling for future recognition

### Viewing Events

- **Dashboard**: Shows recent events and statistics
- **Gallery**: Browse all events with filtering options
- **Settings**: View system information and statistics

## Home Assistant Integration

### Sensors

The add-on automatically creates the following sensors:

- `sensor.doorbell_last_event` - Timestamp of last doorbell event
- `sensor.doorbell_known_faces_today` - Count of known faces detected today
- `sensor.doorbell_unknown_faces_today` - Count of unknown faces detected today
- `binary_sensor.doorbell_person_detected` - Binary sensor for any person detection

### Events

The add-on fires the following events:

- `doorbell_face_detected` - Fired when any face is detected
- `doorbell_known_person` - Fired when a known person is detected
- `doorbell_unknown_person` - Fired when an unknown person is detected

### Automations

Example automation to send notifications:

```yaml
automation:
  - alias: "Doorbell Known Person"
    trigger:
      platform: event
      event_type: doorbell_known_person
    action:
      service: notify.mobile_app_your_phone
      data:
        title: "Doorbell"
        message: "{{ trigger.event.data.person_name }} is at the door"
        data:
          image: "/api/doorbell/image/{{ trigger.event.data.image_path }}"

  - alias: "Doorbell Unknown Person"
    trigger:
      platform: event
      event_type: doorbell_unknown_person
    action:
      service: notify.mobile_app_your_phone
      data:
        title: "Doorbell Alert"
        message: "Unknown person detected at the door"
        data:
          image: "/api/doorbell/image/{{ trigger.event.data.image_path }}"
```

## API Reference

### REST API Endpoints

- `GET /api/events` - Get doorbell events
- `GET /api/persons` - Get all registered persons
- `POST /api/persons` - Create a new person
- `POST /api/persons/{id}/faces` - Add face image to person
- `POST /api/events/{id}/label` - Label an event with a person
- `POST /api/camera/capture` - Manually capture a frame
- `GET /api/settings` - Get current settings
- `GET /api/stats` - Get system statistics

### WebSocket Events

The add-on supports real-time updates via WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:8099/ws');
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    if (data.type === 'face_detected') {
        console.log('Face detected:', data.person_name);
    }
};
```

## Troubleshooting

### Common Issues

**Camera Connection Failed**
- Verify camera URL is correct and accessible
- Check network connectivity between Home Assistant and camera
- Ensure camera supports the specified stream format

**Face Recognition Not Working**
- Verify face images are clear and well-lit
- Adjust confidence threshold in settings
- Ensure multiple face images per person for better accuracy

**High CPU Usage**
- Reduce camera resolution if possible
- Increase capture interval in advanced settings
- Consider using hardware acceleration if available

**Storage Issues**
- Check available disk space
- Adjust retention days to reduce storage usage
- Enable cleanup of old events in settings

### Debug Mode

Enable debug logging by setting the add-on log level to "debug":

1. Go to **Supervisor** → **Add-on Store** → **Doorbell Face Recognition**
2. Click **Configuration** tab
3. Set **Log Level** to "debug"
4. Restart the add-on

### Log Files

View logs in Home Assistant:
- **Supervisor** → **Add-on Store** → **Doorbell Face Recognition** → **Log** tab

## Performance Optimization

### Hardware Requirements

- **Minimum**: 2GB RAM, dual-core CPU
- **Recommended**: 4GB RAM, quad-core CPU
- **Storage**: 10GB free space (depends on retention settings)

### Optimization Tips

1. **Camera Settings**:
   - Use 720p resolution for balance of quality and performance
   - Reduce frame rate if high CPU usage occurs
   - Use H.264 encoding when possible

2. **Face Recognition**:
   - Start with confidence threshold of 0.6
   - Add multiple face images per person (3-5 recommended)
   - Use well-lit, front-facing photos

3. **Storage Management**:
   - Set appropriate retention days (30 days recommended)
   - Enable database encryption only if needed
   - Monitor storage usage in settings

## Security Considerations

### Data Privacy

- All face recognition processing happens locally
- No data is sent to external services
- Face encodings are stored securely in local database
- Optional database encryption for sensitive environments

### Network Security

- Web interface is accessible only within your local network
- Use HTTPS proxy if exposing to internet
- Consider VPN access for remote monitoring

### Access Control

- Integrate with Home Assistant authentication
- Use strong passwords for camera access
- Regularly update the add-on for security patches

## Development

### Building from Source

```bash
git clone https://github.com/Beast12/whorang.git
cd whorang/doorbell-addon
docker build -t doorbell-face-recognition .
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Testing

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/

# Run linting
flake8 src/
black src/
isort src/
```

## Support

### Getting Help

- **Issues**: [GitHub Issues](https://github.com/Beast12/whorang/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Beast12/whorang/discussions)
- **Home Assistant Community**: [Community Forum](https://community.home-assistant.io/)

### Reporting Bugs

When reporting bugs, please include:
- Home Assistant version
- Add-on version
- Camera model and settings
- Relevant log entries
- Steps to reproduce the issue

## Changelog

### Version 1.0.6 (2024-08-20)

- Initial release
- Face recognition using face_recognition library
- Web interface for face management
- Home Assistant integration
- Multi-architecture support
- SQLite database with optional encryption
- Real-time camera monitoring
- Event gallery and filtering
- Configurable settings and notifications

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [face_recognition](https://github.com/ageitgey/face_recognition) library by Adam Geitgey
- [Home Assistant](https://www.home-assistant.io/) community
- [hassio-addons](https://github.com/hassio-addons) base images
- All contributors and testers

---

**Made with ❤️ for the Home Assistant community**
