# Doorbell Face Recognition Add-on

[![Version](https://img.shields.io/badge/version-1.0.66-blue.svg)](https://github.com/Beast12/whorang/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Add--on-blue.svg)](https://www.home-assistant.io/)

AI-powered doorbell with face recognition capabilities for Home Assistant. This add-on provides event-driven face detection and recognition, triggered when your doorbell is pressed, allowing you to identify known visitors and receive notifications when unknown faces are detected at your door.

## Features

- **AI-Powered Face Recognition** - Uses the face_recognition library for accurate face detection and identification
- **Event-Driven Processing** - Face recognition triggered by doorbell ring events, not continuous monitoring
- **Home Assistant Integration** - Native integration with sensors, notifications, and automations
- **Web Interface** - Beautiful, responsive web UI for managing faces and viewing events
- **Privacy-Focused** - All processing happens locally, no cloud dependencies
- **Multi-Platform Support** - Works on amd64, arm64, armv7, and other architectures
- **Local Storage** - SQLite database with optional encryption
- **Flexible Notifications** - Home Assistant notifications and webhook support
- **Event Gallery** - Browse and manage doorbell events with filtering
- **Configurable Settings** - Adjustable confidence thresholds and retention policies

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

1. **Configure Camera**: Set your doorbell camera URL or Home Assistant camera entity in the add-on configuration
2. **Start Add-on**: Enable "Start on boot" and "Auto update" options
3. **Access Web Interface**: Open the add-on web UI (port 8099)
4. **Test Camera**: Use the "Capture" button to test camera connectivity
5. **Setup Doorbell Trigger**: Create Home Assistant automation to trigger face recognition on doorbell press

### Doorbell Integration Setup

This add-on uses **event-driven face recognition** - it only processes images when your doorbell is pressed, not continuously. You need to create a Home Assistant automation that captures an image and sends it to the addon for face recognition.

Here's a comprehensive automation that includes AI-generated descriptions, notifications, and face recognition:

```yaml
alias: Smart Doorbell Notification with AI + Face Recognition
description: Send notification with AI-generated message and process face recognition
triggers:
  - entity_id: binary_sensor.your_doorbell_button  # Replace with your doorbell entity
    from: "off"
    to: "on"
    trigger: state
actions:
  - target:
      entity_id: camera.your_doorbell_camera  # Replace with your camera entity
    data:
      filename: "{{ snapshot_path }}"
    action: camera.snapshot
  - target:
      device_id:
        - your_device_id_1  # Replace with your device IDs for doorbell sound
        - your_device_id_2
        - your_device_id_3
        - your_device_id_4
        - your_device_id_5
        - your_device_id_6
        - your_device_id_7
        - your_device_id_8
        - your_device_id_9
    data:
      media:
        media_content_id: /local/sounds/doorbell.mp3
        media_content_type: music
        metadata: {}
    action: media_player.play_media
    enabled: true
  - data:
      remember: false
      use_memory: false
      include_filename: false
      target_width: 1280
      max_tokens: 100
      temperature: 0.2
      generate_title: true
      expose_images: true
      provider: your_llm_provider_id  # Replace with your LLM provider ID
      message: >-
        You are my sarcastic funny security guard. Describe what you see. Don't
        mention trees, bushes, grass, landscape, driveway, light fixtures, yard,
        brick, wall, garden. Don't mention the time and date. Be precise and
        short in one funny one liner of max 10 words. Only describe the person,
        vehicle or the animal.
      image_file: "{{ snapshot_path }}"
      model: gpt-4o-mini  # Replace with your preferred AI model
    response_variable: ai_description
    action: llmvision.image_analyzer
  - parallel:
      - data:
          message: "{{ ai_description.response_text }}"
          title: "{{ ai_description.title }}"
          data:
            image: /local/doorbell_snapshot_{{ timestamp }}.jpg
            ttl: 0
            priority: high
            clickAction: "{{ snapshot_url }}"
            actions:
              - action: VIEW_PHOTO
                title: 📷 Photo
                uri: "{{ snapshot_url }}"
              - action: OPEN_CAMERA
                title: 📹 Live
                uri: /dashboard-home/cameras
              - action: DISMISS
                title: ❌ Close
        action: notify.mobile_app_your_phone_1  # Replace with your notification service
      - data:
          message: "{{ ai_description.response_text }}"
          title: "{{ ai_description.title }}"
          data:
            image: /local/doorbell_snapshot_{{ timestamp }}.jpg
            ttl: 0
            priority: high
            clickAction: "{{ snapshot_url }}"
            actions:
              - action: VIEW_PHOTO
                title: 📷 Photo
                uri: "{{ snapshot_url }}"
              - action: OPEN_CAMERA
                title: 📹 Live
                uri: /dashboard-home/cameras
              - action: DISMISS
                title: ❌ Close
        action: notify.mobile_app_your_phone_2  # Replace with second notification service
        enabled: true
      # Send to doorbell addon for face recognition
      - action: rest_command.doorbell_ring
        data:
          ai_message: "{{ ai_description.response_text }}"
          ai_title: "{{ ai_description.title }}"
          image_path: "{{ snapshot_path }}"
          image_url: "{{ snapshot_url }}"
      - data:
          media_player_entity_id: media_player.your_display_1  # Replace with your media players
          message: "{{ ai_description.response_text }}"
          cache: true
        action: tts.speak
        target:
          entity_id: tts.google_translate_en_com
        enabled: true
      - data:
          media_player_entity_id: media_player.your_display_2  # Replace with your media players
          message: "{{ ai_description.response_text }}"
          cache: true
        action: tts.speak
        target:
          entity_id: tts.google_translate_en_com
        enabled: true
  - target:
      device_id:
        - your_display_device_id_1  # Replace with your display device IDs
        - your_display_device_id_2
    data:
      media:
        media_content_id: "{{ snapshot_url }}"
        media_content_type: image/jpeg
        metadata: {}
    action: media_player.play_media
    enabled: true
  - delay:
      seconds: 15
  - target:
      device_id:
        - your_display_device_id_1  # Same display device IDs as above
        - your_display_device_id_2
        - your_display_device_id_3
    action: media_player.media_stop
    data: {}
    enabled: true
variables:
  timestamp: "{{ now().timestamp() | int }}"
  snapshot_path: /config/www/doorbell_snapshot_{{ timestamp }}.jpg
  snapshot_url: https://your-ha-domain.com/local/doorbell_snapshot_{{ timestamp }}.jpg  # Replace with your HA URL
```

**Required REST Command** - Add this to your `configuration.yaml`:

```yaml
rest_command:
  doorbell_ring:
    url: "http://a0d7b954-doorbell-face-recognition:8099/api/doorbell/ring"
    method: POST
    headers:
      Content-Type: "application/x-www-form-urlencoded"
    payload: >-
      ai_message={{ ai_message | urlencode }}&ai_title={{ ai_title | urlencode }}&image_path={{ image_path | urlencode }}&image_url={{ image_url | urlencode }}
    timeout: 30
```

**Important Replacements Needed:**
- `binary_sensor.your_doorbell_button` - Your doorbell button entity
- `camera.your_doorbell_camera` - Your doorbell camera entity  
- `your_device_id_*` - Your device IDs for speakers/displays (9 total for doorbell sound)
- `your_llm_provider_id` - Your LLM Vision provider ID
- `notify.mobile_app_your_phone_*` - Your mobile notification services
- `media_player.your_display_*` - Your media player entities for TTS
- `your_display_device_id_*` - Your display device IDs for showing images
- `https://your-ha-domain.com` - Your Home Assistant external URL

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

### Additional Automations

You can create additional automations to respond to face recognition events:

```yaml
automation:
  - alias: "Doorbell Known Person Detected"
    trigger:
      platform: event
      event_type: doorbell_known_person
    action:
      - service: notify.mobile_app_your_phone  # Replace with your notification service
        data:
          title: "Welcome Home!"
          message: "{{ trigger.event.data.person_name }} is at the door"
          data:
            image: "/api/doorbell/image/{{ trigger.event.data.image_path }}"
      - service: light.turn_on  # Optional: Turn on lights for known persons
        target:
          entity_id: light.front_porch

  - alias: "Doorbell Unknown Person Alert"
    trigger:
      platform: event
      event_type: doorbell_unknown_person
    action:
      - service: notify.mobile_app_your_phone  # Replace with your notification service
        data:
          title: "Security Alert"
          message: "Unknown person detected at the door"
          data:
            image: "/api/doorbell/image/{{ trigger.event.data.image_path }}"
      - service: light.turn_on  # Optional: Turn on security lights
        target:
          entity_id: light.security_lights
        data:
          brightness: 255

  - alias: "Daily Face Recognition Summary"
    trigger:
      platform: time
      at: "23:00:00"
    action:
      service: notify.mobile_app_your_phone  # Replace with your notification service
      data:
        title: "Daily Doorbell Summary"
        message: >
          Today: {{ states('sensor.doorbell_known_faces_today') }} known visitors, 
          {{ states('sensor.doorbell_unknown_faces_today') }} unknown visitors
```

## API Reference

### REST API Endpoints

- `GET /api/events` - Get doorbell events
- `GET /api/persons` - Get all registered persons
- `POST /api/persons` - Create a new person
- `POST /api/persons/{id}/faces` - Add face image to person
- `POST /api/events/{id}/label` - Label an event with a person
- `POST /api/camera/capture` - Manually capture a frame
- `POST /api/doorbell/ring` - **NEW**: Trigger doorbell ring event with face recognition
- `GET /api/settings` - Get current settings
- `GET /api/stats` - Get system statistics


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

**No Events Being Created**
- Ensure doorbell automation is configured to call `/api/doorbell/ring`
- Test manual capture to verify camera connectivity
- Check that doorbell entity is triggering the automation

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
docker build -t whorang-doorbell-addon .
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

## v1.0.20 (Latest)
- Fixed template loading and import paths for containerized environment
- Resolved settings and gallery page 404 errors
- Corrected absolute file paths (/app/web/templates, /app/web/static)
- Fixed relative imports to use proper module structure
- Added database dependency injection to FaceRecognitionManager
- All linting checks pass (flake8, black, isort, mypy)

## v1.0.13
- Fixed Docker image name in config.yaml to match actual build output
- Corrected image reference from doorbell-face-recognition to whorang-doorbell-addon

## v1.0.10
- Fixed repository metadata update detached HEAD issue
- Improved git push logic to avoid empty commits

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [face_recognition](https://github.com/ageitgey/face_recognition) library by Adam Geitgey
- [Home Assistant](https://www.home-assistant.io/) community
- [hassio-addons](https://github.com/hassio-addons) base images
- All contributors and testers

---

**Made with ❤️ for the Home Assistant community**
