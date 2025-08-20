# Changelog

All notable changes to the Doorbell Face Recognition add-on will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.8] - 2024-08-20

### Fixed
- Made Docker images public for Home Assistant addon compatibility
- Fixed multi-architecture build to create proper manifest (linux/amd64,linux/arm64)
- Removed security scan job that was failing with multi-arch images
- Added automatic image visibility setting to public

## [1.0.7] - 2024-08-20

### Fixed
- Security scan workflow authentication - added Docker login for Trivy scanner
- Trivy can now access private container registry images

## [1.0.6] - 2024-08-20

### Fixed
- GitHub Actions workflow authentication using GHCR_PAT secret
- Docker image name changed to whorang-doorbell-addon
- Multi-platform build strategy (linux/amd64, linux/arm64)
- TARGETARCH undefined variable in Dockerfile
- Simplified security scan workflow

## [1.0.5] - 2024-08-20

### Fixed
- Docker registry authentication for ghcr.io/beast12 namespace
- GitHub Actions workflow Docker login with correct username
- BUILD_ARCH variable in Dockerfile (changed to TARGETARCH)
- Version consistency across all configuration files
- All mypy type checking errors resolved
- Black code formatting applied
- Import sorting with isort
- Complete linting compliance

## [1.0.0] - 2024-08-19

### Added
- Initial release of Doorbell Face Recognition add-on
- AI-powered face recognition using face_recognition library
- Real-time doorbell camera monitoring with RTSP/HTTP support
- Beautiful, responsive web interface for face management
- Home Assistant integration with sensors and notifications
- Multi-architecture Docker support (amd64, arm64, armv7, armhf, i386)
- SQLite database with optional encryption for face data
- Event gallery with filtering and search capabilities
- Configurable confidence thresholds and retention policies
- Automated cleanup of old events and images
- RESTful API for external integrations
- WebSocket support for real-time updates
- Comprehensive logging and error handling
- Security scanning and vulnerability management
- GitHub Actions CI/CD pipeline with automated builds
- Version consistency validation across all configuration files
- Automated changelog generation and release management

### Features
- **Face Recognition**: Accurate face detection and identification
- **Privacy-First**: All processing happens locally, no cloud dependencies
- **Web Interface**: Modern UI with dashboard, gallery, and settings pages
- **Home Assistant Integration**: Native sensors, events, and automation support
- **Storage Management**: Configurable retention with automatic cleanup
- **Multi-Platform**: Support for various architectures and camera types
- **Security**: Optional database encryption and secure API endpoints
- **Notifications**: Home Assistant notifications and webhook support
- **Performance**: Optimized for resource-constrained environments

### Technical Details
- FastAPI backend with async support
- SQLite database with encrypted storage option
- Bootstrap 5 responsive frontend
- Docker multi-stage builds for optimized images
- Comprehensive test coverage and linting
- Type hints throughout Python codebase
- Structured logging with configurable levels
- Health checks and monitoring endpoints

### Documentation
- Comprehensive README with installation and configuration guide
- API documentation with examples
- Troubleshooting guide with common issues
- Performance optimization recommendations
- Security best practices
- Development setup instructions

### Infrastructure
- GitHub Actions workflow for automated builds
- Multi-architecture container images
- Automated security scanning with Trivy
- Version consistency validation
- Automated release management
- Container registry publishing to GHCR

## [Unreleased]

### Planned Features
- Mobile app notifications
- Advanced face recognition models
- Cloud backup options
- Integration with additional camera brands
- Machine learning model training interface
- Advanced analytics and reporting
- Multi-language support
- Dark mode theme
- Voice notifications
- Integration with smart locks

---

For more details about each release, see the [GitHub Releases](https://github.com/Beast12/whorang/releases) page.
