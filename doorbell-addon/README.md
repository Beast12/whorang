# Doorbell Face Recognition Add-on - Technical Documentation

This document contains technical details for the WhoRang Doorbell Face Recognition add-on.

> **For user documentation, installation, and setup instructions, see the [main README](../README.md).**

## Add-on Information

- **Name**: Doorbell Face Recognition
- **Version**: 1.0.75
- **Slug**: `doorbell_face_recognition`
- **Architecture Support**: amd64, aarch64
- **Base Image**: ghcr.io/hassio-addons/base:18.1.0

## Directory Structure

```
doorbell-addon/
├── src/                    # Python source code
│   ├── app.py             # FastAPI application
│   ├── config.py          # Configuration management
│   ├── database.py        # Database models and operations
│   ├── face_recognition.py # Face recognition logic
│   ├── ha_camera.py       # Home Assistant camera integration
│   ├── ha_integration.py  # Home Assistant sensors and events
│   └── utils.py           # Utility functions
├── web/                   # Web interface
│   ├── static/           # CSS, JS, images
│   └── templates/        # Jinja2 HTML templates
├── config.yaml           # Add-on configuration
├── build.yaml            # Docker build configuration
├── Dockerfile            # Container definition
├── requirements.txt      # Python dependencies
├── run.sh               # Startup script
└── CHANGELOG.md         # Version history
```

## API Endpoints

### Events
- `GET /api/events` - List doorbell events
- `GET /api/events/{id}` - Get specific event
- `DELETE /api/events` - Delete multiple events
- `POST /api/doorbell/ring` - Trigger face recognition

### Persons
- `GET /api/persons` - List all persons
- `POST /api/persons` - Create new person
- `PUT /api/persons/{id}` - Update person name
- `DELETE /api/persons/{id}` - Delete person
- `POST /api/persons/{id}/faces` - Add face image

### Camera
- `GET /api/camera/entities` - List available camera entities
- `POST /api/camera/capture` - Manual camera capture
- `POST /api/camera/test` - Test camera connection

### Settings
- `GET /api/settings` - Get current settings
- `POST /api/settings` - Update settings

### Weather
- `GET /api/weather-entities` - List weather entities

### System
- `GET /api/stats` - System statistics
- `GET /health` - Health check

## Database Schema

### Tables

**persons**
- `id` INTEGER PRIMARY KEY
- `name` TEXT UNIQUE NOT NULL
- `created_at` TIMESTAMP
- `updated_at` TIMESTAMP

**face_encodings**
- `id` INTEGER PRIMARY KEY
- `person_id` INTEGER (FK to persons)
- `encoding` TEXT (encrypted 128-D face vector)
- `confidence` REAL
- `created_at` TIMESTAMP

**doorbell_events**
- `id` INTEGER PRIMARY KEY
- `timestamp` TIMESTAMP
- `image_path` TEXT
- `person_id` INTEGER (FK to persons, nullable)
- `confidence` REAL (nullable)
- `is_known` BOOLEAN
- `processed` BOOLEAN
- `ai_message` TEXT (nullable)
- `weather_condition` TEXT (nullable)
- `weather_temperature` REAL (nullable)
- `weather_humidity` REAL (nullable)

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `camera_entity` | string | "" | Home Assistant camera entity ID |
| `camera_url` | string | Required | RTSP or HTTP camera URL |
| `storage_path` | string | `/share/doorbell` | Storage location |
| `retention_days` | int | 30 | Event retention period (1-365) |
| `face_confidence_threshold` | float | 0.6 | Recognition threshold (0.1-1.0) |
| `notification_webhook` | string | "" | Webhook URL for notifications |
| `database_encryption` | bool | false | Enable face data encryption |
| `ha_access_token` | string | "" | Home Assistant long-lived token |

## Environment Variables

The add-on uses these environment variables (set automatically by Home Assistant):

- `HASSIO_TOKEN` - Supervisor API token
- `SUPERVISOR_TOKEN` - Alternative supervisor token
- `CAMERA_URL` - Camera stream URL
- `CAMERA_ENTITY` - Camera entity ID
- `STORAGE_PATH` - Data storage path
- `RETENTION_DAYS` - Event retention days
- `FACE_CONFIDENCE_THRESHOLD` - Recognition threshold
- `NOTIFICATION_WEBHOOK` - Webhook URL
- `DATABASE_ENCRYPTION` - Encryption flag
- `HA_ACCESS_TOKEN` - Home Assistant API token
- `WEATHER_ENTITY` - Weather entity ID

## Dependencies

### Python Packages
- `fastapi==0.104.1` - Web framework
- `uvicorn[standard]==0.24.0` - ASGI server
- `face-recognition>=1.3.0` - Face recognition library
- `opencv-python-headless>=4.9.0.80` - Image processing
- `dlib>=19.24.2` - Machine learning toolkit
- `numpy>=1.24.0` - Numerical computing
- `sqlalchemy==2.0.23` - Database ORM
- `cryptography>=42.0.0` - Encryption
- `pydantic==2.5.0` - Data validation
- `structlog==23.2.0` - Structured logging

### System Packages
- `python3` - Python runtime
- `ffmpeg` - Video processing
- `gstreamer` - Streaming media framework
- `py3-opencv` - OpenCV system package
- `gcc`, `g++`, `cmake` - Build tools
- `blas-dev`, `lapack-dev`, `gfortran` - Math libraries

## Face Recognition Technical Details

### Algorithm
- Uses dlib's ResNet-based face detection
- Extracts 128-dimensional face encodings
- Compares using Euclidean distance
- Configurable tolerance threshold

### Performance
- Face detection: ~1-3 seconds per image
- Face encoding: ~0.5-1 second per face
- Face comparison: ~0.01 seconds per known face
- Memory usage: ~100-200MB base + ~1MB per known face

### Accuracy
- Face detection: ~95% accuracy in good lighting
- Face recognition: ~99% accuracy with quality training images
- False positive rate: <1% with default threshold (0.6)

## Storage

### File Locations
- **Database**: `/share/doorbell/database/doorbell.db`
- **Images**: `/share/doorbell/images/`
- **Face thumbnails**: `/share/doorbell/faces/`
- **Config**: `/share/doorbell/config/settings.json`
- **Encryption key**: `/share/doorbell/database/.key`

### Storage Requirements
- Database: ~1MB per 1000 events
- Images: ~200KB per event (JPEG)
- Face encodings: ~1KB per face
- Estimated: ~200MB per 1000 events

## Home Assistant Integration

### Sensors Created
- `sensor.doorbell_last_event`
- `sensor.doorbell_known_faces_today`
- `sensor.doorbell_unknown_faces_today`
- `sensor.doorbell_total_events`
- `sensor.doorbell_person_detected`
- `sensor.doorbell_confidence`

### Events Fired
- `doorbell_face_detected` - Any face detected
- `doorbell_known_person` - Known person recognized
- `doorbell_unknown_person` - Unknown person detected

### Event Data Structure
```json
{
  "event_id": 123,
  "timestamp": "2024-10-24T12:00:00",
  "person_id": 5,
  "person_name": "John Doe",
  "confidence": 0.92,
  "faces_detected": 1,
  "image_path": "/share/doorbell/images/doorbell_20241024_120000.jpg",
  "image_url": "https://ha.example.com/local/doorbell_snapshot_123.jpg",
  "ai_message": "Just a friendly neighbor stopping by",
  "weather_condition": "sunny",
  "weather_temperature": 22.5,
  "weather_humidity": 65
}
```

## Security

### Authentication
- Uses Home Assistant ingress authentication
- Supervisor token for API access
- Optional long-lived token for external access

### Data Protection
- Optional AES-256 encryption for face encodings
- Local processing only - no cloud services
- Secure key storage with restricted permissions
- HTTPS through Home Assistant proxy

### Privacy
- All data stored locally
- No external API calls (except optional AI/weather)
- Face data encrypted at rest (if enabled)
- Configurable data retention

## Logging

### Log Levels
- `INFO` - Normal operations
- `WARNING` - Non-critical issues
- `ERROR` - Errors requiring attention
- `DEBUG` - Detailed debugging (disabled by default)

### Log Locations
- Container logs: `docker logs addon_doorbell_face_recognition`
- Home Assistant logs: Settings → System → Logs
- Structured logging with context fields

## Troubleshooting

### Common Issues

**Face recognition not loading:**
- Check if dlib/face_recognition installed correctly
- Verify sufficient RAM available
- Check container logs for import errors

**Camera connection fails:**
- Test RTSP URL with VLC
- Verify network connectivity
- Check camera credentials
- Try Home Assistant camera entity instead

**High CPU usage:**
- Face recognition is CPU-intensive
- Consider reducing capture frequency
- Use event-driven approach (not continuous)
- Upgrade to more powerful hardware

**Database errors:**
- Check disk space
- Verify write permissions
- Disable encryption if causing issues
- Check for corrupted database file

## Development

### Local Testing
See [TESTING.md](TESTING.md) for local development setup.

### Building
```bash
docker build -t doorbell-face-recognition .
```

### Linting
```bash
flake8 src/
black src/
isort --profile black src/
mypy src/ --config-file mypy.ini
```

## Version History

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

## License

MIT License - see [LICENSE](../LICENSE) file.

## Links

- **Main Documentation**: [../README.md](../README.md)
- **Automation Examples**: [AUTOMATION.md](AUTOMATION.md)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)
- **Testing Guide**: [TESTING.md](TESTING.md)
- **GitHub Repository**: https://github.com/Beast12/whorang
- **Issues**: https://github.com/Beast12/whorang/issues
