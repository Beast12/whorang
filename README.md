# Doorbell Face Recognition - Home Assistant Add-on

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/Beast12/whorang/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Add--on-blue.svg)](https://www.home-assistant.io/)
[![Build](https://github.com/Beast12/whorang/workflows/Build%20and%20Publish%20Doorbell%20Face%20Recognition%20Addon/badge.svg)](https://github.com/Beast12/whorang/actions)

A production-ready Home Assistant community add-on that replicates Google Nest Doorbell functionality with AI-powered face recognition capabilities. This add-on provides real-time face detection, recognition, and a beautiful web interface for managing your doorbell security system.

## 🚀 Quick Start

1. **Add Repository**: Add `https://github.com/Beast12/whorang` to your Home Assistant add-on repositories
2. **Install**: Find "Doorbell Face Recognition" in the add-on store and install
3. **Configure**: Set your camera URL and preferences
4. **Start**: Enable and start the add-on
5. **Access**: Open the web UI and start adding faces

## ✨ Key Features

- 🎯 **AI-Powered Face Recognition** - Uses face_recognition library for accurate identification
- 📹 **Real-time Monitoring** - Continuous doorbell camera surveillance
- 🏠 **Native Home Assistant Integration** - Sensors, notifications, and automations
- 🖥️ **Beautiful Web Interface** - Modern, responsive UI for face management
- 🔒 **Privacy-First** - All processing happens locally, no cloud dependencies
- 📱 **Multi-Architecture** - Supports amd64, arm64, armv7, and more
- 🗄️ **Secure Storage** - SQLite with optional encryption
- 🔔 **Smart Notifications** - Home Assistant and webhook notifications
- 📊 **Event Management** - Gallery view with filtering and search
- ⚙️ **Highly Configurable** - Adjustable thresholds and retention policies

## 📋 Requirements

- Home Assistant OS, Supervised, or Container
- Compatible doorbell camera with RTSP/HTTP stream
- Minimum 2GB RAM (4GB recommended)
- 10GB free storage space

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Doorbell      │    │   Home Assistant │    │   Web Interface │
│   Camera        │────│   Add-on         │────│   (Port 8099)   │
│   (RTSP/HTTP)   │    │   Face Recognition│    │   Management UI │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │   Local Storage  │
                       │   • Images       │
                       │   • Face Data    │
                       │   • Events       │
                       └──────────────────┘
```

## 📖 Documentation

- **[Installation Guide](doorbell-addon/README.md#installation)** - Step-by-step setup instructions
- **[Configuration](doorbell-addon/README.md#configuration)** - All configuration options explained
- **[API Reference](doorbell-addon/README.md#api-reference)** - REST API and WebSocket documentation
- **[Troubleshooting](doorbell-addon/README.md#troubleshooting)** - Common issues and solutions
- **[Home Assistant Integration](doorbell-addon/README.md#home-assistant-integration)** - Sensors and automations

## 🛠️ Development

### Building

```bash
git clone https://github.com/Beast12/whorang.git
cd whorang/doorbell-addon
docker build -t doorbell-face-recognition .
```

### Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run linting
flake8 src/
black src/
isort src/

# Type checking
mypy src/
```

### CI/CD Pipeline

This project uses GitHub Actions for:
- ✅ Multi-architecture builds (amd64, arm64, armv7, armhf, i386)
- ✅ Automated testing and linting
- ✅ Security scanning with Trivy
- ✅ Version consistency validation
- ✅ Automated releases with changelog generation
- ✅ Container registry publishing (GHCR)

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 Changelog

### v1.0.0 (2024-08-19)
- 🎉 Initial release
- ✨ Face recognition with face_recognition library
- 🖥️ Responsive web interface
- 🏠 Home Assistant integration
- 🐳 Multi-architecture Docker support
- 🔒 Optional database encryption
- 📊 Event gallery and management
- ⚙️ Configurable settings

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [face_recognition](https://github.com/ageitgey/face_recognition) by Adam Geitgey
- [Home Assistant](https://www.home-assistant.io/) community
- [hassio-addons](https://github.com/hassio-addons) base images
- All contributors and beta testers

## 🆘 Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/Beast12/whorang/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/Beast12/whorang/discussions)
- 🏠 **Community**: [Home Assistant Forum](https://community.home-assistant.io/)

---

**⭐ If you find this project useful, please consider giving it a star!**

**Made with ❤️ for the Home Assistant community**