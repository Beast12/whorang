# Doorbell Face Recognition Add-on

[![Version](https://img.shields.io/badge/version-1.0.74-blue.svg)](https://github.com/Beast12/whorang/releases)
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

This add-on uses **event-driven face recognition** - it only processes images when your doorbell is pressed, not continuously. Follow these steps to integrate it with your Home Assistant setup:

#### Step 1: Add REST Command to Configuration

Add this REST command to your Home Assistant `configuration.yaml` file. This allows automations to send doorbell events to the face recognition addon.

```yaml
rest_command:
  doorbell_ring:
    url: "http://d4f73725-doorbell-face-recognition:8099/api/doorbell/ring"
    method: POST
    headers:
      Content-Type: "application/x-www-form-urlencoded"
    payload: >-
      ai_message={{ ai_message | urlencode }}&ai_title={{ ai_title | urlencode }}&image_path={{ image_path | urlencode }}&image_url={{ image_url | urlencode }}
    timeout: 30
```

> **Note:** The URL `http://d4f73725-doorbell-face-recognition:8099` is the internal Home Assistant addon address. The slug `d4f73725-doorbell-face-recognition` may vary - check your addon details page for the exact address.

After adding this, **restart Home Assistant** to load the REST command.

#### Step 2: Create Doorbell Automation

Create an automation that triggers when your doorbell is pressed. This example includes AI-powered descriptions, mobile notifications, TTS announcements, and face recognition.

**Option A: Simple Automation (Face Recognition Only)**

If you just want face recognition without AI descriptions:

```yaml
alias: Simple Doorbell Face Recognition
description: Trigger face recognition when doorbell is pressed
triggers:
  - entity_id: binary_sensor.your_doorbell_button
    from: "off"
    to: "on"
    trigger: state
actions:
  - target:
      entity_id: camera.your_doorbell_camera
    data:
      filename: "{{ snapshot_path }}"
    action: camera.snapshot
  - action: rest_command.doorbell_ring
    data:
      ai_message: "Doorbell pressed"
      ai_title: "Visitor at the door"
      image_path: "{{ snapshot_path }}"
      image_url: "{{ snapshot_url }}"
variables:
  timestamp: "{{ now().timestamp() | int }}"
  snapshot_path: /config/www/doorbell_snapshot_{{ timestamp }}.jpg
  snapshot_url: https://your-home-assistant-url.com/local/doorbell_snapshot_{{ timestamp }}.jpg
```

**Option B: Advanced Automation (AI + Face Recognition + Notifications)**

Full-featured automation with AI-generated descriptions, notifications, and face recognition:

```yaml
alias: Smart Doorbell Notification with AI
description: Send notification with AI-generated message when doorbell is pressed
triggers:
  - entity_id: binary_sensor.your_doorbell_button
    from: "off"
    to: "on"
    trigger: state
actions:
  # 1. Capture snapshot from doorbell camera
  - target:
      entity_id: camera.your_doorbell_camera
    data:
      filename: "{{ snapshot_path }}"
    action: camera.snapshot
  
  # 2. Play doorbell sound on speakers (optional)
  - target:
      device_id:
        - device_id_speaker_1
        - device_id_speaker_2
        - device_id_speaker_3
    data:
      media:
        media_content_id: /local/sounds/doorbell.mp3
        media_content_type: music
        metadata: {}
    action: media_player.play_media
    enabled: true
  
  # 3. Generate AI description of who's at the door (requires LLM Vision integration)
  - data:
      remember: false
      use_memory: false
      include_filename: false
      target_width: 1280
      max_tokens: 100
      temperature: 0.2
      generate_title: true
      expose_images: true
      provider: your_llm_provider_id
      message: >-
        You are my sarcastic funny security guard. Describe what you see. Don't
        mention trees, bushes, grass, landscape, driveway, light fixtures, yard,
        brick, wall, garden. Don't mention the time and date. Be precise and
        short in one funny one liner of max 10 words. Only describe the person,
        vehicle or the animal.
      image_file: "{{ snapshot_path }}"
      model: gpt-4o-mini
    response_variable: ai_description
    action: llmvision.image_analyzer
  
  # 4. Send notifications and process face recognition in parallel
  - parallel:
      # Send mobile notification to first phone
      - action: notify.mobile_app_phone_1
        data:
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
      
      # Send mobile notification to second phone
      - action: notify.mobile_app_phone_2
        data:
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
        enabled: true
      
      # Send to face recognition addon
      - action: rest_command.doorbell_ring
        data:
          ai_message: "{{ ai_description.response_text }}"
          ai_title: "{{ ai_description.title }}"
          image_path: "{{ snapshot_path }}"
          image_url: "{{ snapshot_url }}"
      
      # Announce via TTS on display 1
      - data:
          media_player_entity_id: media_player.kitchen_display
          message: "{{ ai_description.response_text }}"
          cache: true
        action: tts.speak
        target:
          entity_id: tts.google_translate_en_com
        enabled: true
      
      # Announce via TTS on display 2
      - data:
          media_player_entity_id: media_player.office_display
          message: "{{ ai_description.response_text }}"
          cache: true
        action: tts.speak
        target:
          entity_id: tts.google_translate_en_com
        enabled: true
  
  # 5. Show snapshot on displays
  - target:
      device_id:
        - device_id_display_1
        - device_id_display_2
    data:
      media:
        media_content_id: "{{ snapshot_url }}"
        media_content_type: image/jpeg
        metadata: {}
    action: media_player.play_media
    enabled: true
  
  # 6. Wait 15 seconds then stop displaying
  - delay:
      seconds: 15
  
  # 7. Stop media playback on displays
  - target:
      device_id:
        - device_id_display_1
        - device_id_display_2
    action: media_player.media_stop
    data: {}
    enabled: true

variables:
  timestamp: "{{ now().timestamp() | int }}"
  snapshot_path: /config/www/doorbell_snapshot_{{ timestamp }}.jpg
  snapshot_url: https://your-home-assistant-url.com/local/doorbell_snapshot_{{ timestamp }}.jpg
```

#### Step 3: Customize the Automation

Replace these placeholders with your actual entities and settings:

| Placeholder | Replace With | How to Find |
|-------------|--------------|-------------|
| `binary_sensor.your_doorbell_button` | Your doorbell button entity | Developer Tools → States → Search for "doorbell" |
| `camera.your_doorbell_camera` | Your doorbell camera entity | Settings → Devices → Your Camera → Entities |
| `device_id_speaker_*` | Device IDs for speakers | Settings → Devices → Click device → Copy device ID from URL |
| `device_id_display_*` | Device IDs for displays | Settings → Devices → Click device → Copy device ID from URL |
| `your_llm_provider_id` | Your LLM Vision provider ID | LLM Vision integration settings |
| `notify.mobile_app_phone_*` | Your mobile notification service | Developer Tools → Services → Search "notify" |
| `media_player.kitchen_display` | Your media player entities | Developer Tools → States → Search "media_player" |
| `https://your-home-assistant-url.com` | Your Home Assistant external URL | Settings → System → Network → External URL |

#### Step 4: Test the Integration

1. **Save the automation** in Home Assistant
2. **Press your doorbell** to trigger the automation
3. **Check the addon web interface** - you should see a new event in the dashboard
4. **Verify face recognition** - if you've added people, they should be recognized

#### Troubleshooting

- **No events appearing?** Check Home Assistant logs for REST command errors
- **Face recognition not working?** Ensure you've added people with face images first
- **AI descriptions not showing?** The LLM Vision integration is optional - face recognition works without it
- **Wrong addon URL?** Check Settings → Add-ons → Doorbell Face Recognition → Info for the correct slug

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

## 💖 **Support the Project**

If you find WhoRang-addon useful, consider supporting its development:

<div align="center">

<a href="https://www.buymeacoffee.com/koen1203" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" >
</a>

**Or scan the QR code:**

<img src="bmc_qr.png" alt="Buy Me A Coffee QR Code" width="150" height="150">

*Your support helps maintain and improve WhoRang-addon!*

</div>

**Made with ❤️ for the Home Assistant community**
