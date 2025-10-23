# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.71] - 2025-10-23

### Added
- **Dashboard Cards Clickable:** All dashboard stat cards now navigate to relevant pages
  - Total Events → Gallery (all events)
  - Known Faces → Gallery (filtered to known faces)
  - Unknown Faces → Gallery (filtered to unknown faces)
  - Registered People → New People management page
- **People Management Page:** Comprehensive CRUD interface for managing registered people
  - View all registered people with face encoding counts
  - Add new people with modal dialog
  - Rename existing people
  - Delete people with confirmation (cascade deletes face encodings)
  - Add face images to people
  - View events for specific people
- **Gallery URL Filtering:** Auto-apply filters based on URL parameters (?filter=known/unknown)
- **Navigation Menu:** Added "People" link to main navigation

### Technical
- Added `/people` page route with full template
- Added `PUT /api/persons/{person_id}` endpoint for updating person names
- Added `DELETE /api/persons/{person_id}` endpoint for deleting persons
- Added `update_person_name()` and `delete_person()` methods to DatabaseManager
- Modified `GET /api/persons` to return array directly (instead of wrapped object)
- Enhanced gallery.html with URL parameter handling on page load
- Improved error handling for duplicate person names in update operations

### User Impact
- Better navigation and discoverability of features
- Quick access to filtered event views from dashboard
- Full people management without needing to use API directly
- Cleaner interface for managing face recognition database
- One-click access to person-specific events

## [1.0.70] - 2025-10-23

### Fixed
- **Person Creation Error:** Fixed duplicate person name error when labeling events
- **Error Handling:** Improved error messages for SQLite IntegrityError (duplicate names)
- **User Experience:** Clear error message now shown: "A person with the name 'X' already exists"

### Technical
- Added sqlite3.IntegrityError exception handling in /api/persons endpoint
- Improved frontend error parsing in dashboard.html and gallery.html
- Better error message propagation from backend to frontend
- Proper HTTP 400 status code for duplicate name errors

### User Impact
- No more "Unexpected non-whitespace character after JSON" errors
- Clear, actionable error messages when trying to create duplicate person names
- Better user experience when labeling events

## [1.0.69] - 2025-10-03

### Fixed
- **Weather Integration Bug:** Fixed weather entity not being saved to persistent storage
- **Settings API Bug:** Added missing weather_entity handling in /api/settings endpoint
- **Configuration Persistence:** Weather entity selection now properly persists across addon restarts

### Technical
- Added weather_entity to save_to_file() method in config.py
- Added weather_entity to load_from_file() method in config.py
- Added weather_entity handling in POST /api/settings endpoint
- Added weather_entity to GET /api/settings response
- Enhanced logging for weather entity updates

### User Impact
- Weather entity selection now saves properly in settings
- Weather data should now appear in doorbell events
- Settings page weather dropdown will retain selected value
- Weather integration fully functional

## [1.0.68] - 2025-10-03

### Fixed
- **CRITICAL HOTFIX:** Fixed persistent "Method Not Allowed" error for /docs endpoint
- Changed from @app.get() to @app.api_route() with multiple HTTP methods support
- Added support for GET, POST, PUT, DELETE, OPTIONS methods for ingress compatibility
- Resolved Home Assistant ingress proxy routing incompatibility

### Technical
- Used @app.api_route("/docs", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
- Maintained simple HTML documentation approach
- Fixed ingress routing issues that caused 405 errors
- Future-proof solution for any HTTP method the proxy might send

## [1.0.67] - 2025-09-26

### Fixed
- **FINAL FIX:** Replaced complex Swagger UI with simple, working HTML API documentation
- Removed dependency on OpenAPI schema generation that doesn't work with ingress
- Created comprehensive, static API documentation page at /docs
- Eliminated all FastAPI automatic documentation features causing issues

### Technical
- Removed unused imports (get_swagger_ui_html, get_redoc_html)
- Created custom HTML documentation with all endpoints listed
- Simple, reliable solution that works in all environments
- Clean, professional styling with endpoint categorization

### API Documentation Features
- Complete endpoint listing with HTTP methods and descriptions
- Organized by categories: System, Events, Persons, Settings, Weather, Images, Web Interface
- Professional styling with color-coded HTTP methods
- No external dependencies - works offline and through any proxy

## [1.0.66] - 2025-09-26

### Fixed
- **Critical Bug:** Fixed OpenAPI schema "Not Found" error for /openapi.json
- Added explicit /openapi.json route handler to ensure proper schema serving
- Enhanced middleware bypass logic for API documentation routes
- API documentation now fully functional through Home Assistant ingress

### Technical
- Added custom get_openapi_schema() route handler
- Improved IngressAuthMiddleware path matching for API docs
- Enhanced route exclusion logic for better compatibility
- All linting checks pass (mypy, flake8, black, isort)

## [1.0.65] - 2025-09-26

### Fixed
- **Critical Bug:** Fixed API documentation "Method Not Allowed" error
- API docs at /docs and /redoc now work properly through Home Assistant ingress
- Added middleware bypass for API documentation routes
- Created custom Swagger UI and ReDoc routes with CDN assets
- Disabled automatic FastAPI docs generation to prevent conflicts

### Technical
- Updated IngressAuthMiddleware to skip API docs paths (/docs, /redoc, /openapi.json)
- Added custom routes using get_swagger_ui_html() and get_redoc_html()
- Used external CDN links for Swagger UI and ReDoc static assets
- Fixed syntax errors in route definitions

## [1.0.64] - 2025-09-25

### Added
- **API Documentation:** Enhanced OpenAPI documentation with Swagger UI
- Interactive API documentation available at `/api/docs`
- ReDoc documentation available at `/api/redoc`
- Added `/api-docs` redirect route for easy access
- Organized API endpoints with proper tags (Events, Persons, Settings, Weather, Camera, System)

### Enhanced
- Comprehensive endpoint descriptions with parameter details
- Better API discoverability and usability for developers
- Interactive API testing through Swagger UI
- Improved documentation for integration purposes

### Technical
- Set docs_url to `/api/docs` (always available, not debug-only)
- Added detailed docstrings for all major API endpoints
- Proper HTTP method documentation for all routes
- Enhanced OpenAPI schema generation

## [1.0.63] - 2025-09-25

### Fixed
- **Critical Bug:** Fixed AttributeError in database row access for weather fields
- sqlite3.Row objects don't have .get() method - changed to proper key checking
- Dashboard now loads correctly without 500 errors when accessing weather data
- Backward compatibility maintained for databases without weather columns

### Technical
- Updated get_doorbell_events() and get_doorbell_event() methods in database.py
- Changed `row.get("field")` to `row["field"] if "field" in row.keys() else None`
- Proper handling of missing weather columns in existing database records
- No database migration required - graceful degradation for missing fields

## [1.0.62] - 2025-09-24

### Added
- **Weather Integration:** Added comprehensive weather data capture for doorbell events
- Weather entity selector in settings page to choose Home Assistant weather source
- Weather conditions, temperature, and humidity automatically captured with each event
- Weather display in dashboard table with condition icons and temperature/humidity
- Weather information in gallery event cards with proper styling
- New API endpoint `/api/weather-entities` to fetch available weather entities
- Database schema updated with weather fields (condition, temperature, humidity)

### Technical
- Added `weather_entity` configuration setting for user-selectable weather source
- Enhanced `process_doorbell_image()` to fetch and store weather data automatically
- Updated database models and migration for weather data storage
- Added weather data display with Bootstrap icons in UI templates
- Weather data persists with events and survives addon restarts

## [1.0.61] - 2025-09-24

### Fixed
- **UI:** Fixed AI message visibility in dashboard and gallery views
- Changed AI message text color from blue to light gray for better readability on dark backgrounds
- Added AI message display to gallery cards with proper contrast styling
- AI messages now clearly visible with italic formatting and quotes

## [1.0.60] - 2025-09-24

### Fixed
- **CRITICAL:** Fixed ingress API path routing causing 401 Unauthorized errors
- Changed all API calls from absolute paths (/api/*) to relative paths (api/*)
- Resolved "Login attempt with invalid authentication" errors in Home Assistant logs
- Fixed event deletion, person creation, and settings API calls through ingress proxy

## [1.0.59] - 2025-09-24

### Fixed
- 401 Unauthorized error in event deletion functionality
- Added Home Assistant ingress authentication middleware for proper session handling
- Implemented CORS preflight request handling for ingress compatibility
- Enhanced FastAPI configuration for Home Assistant addon ingress support

## [1.0.58] - 2025-09-23

### Fixed
- 405 Method Not Allowed error in event deletion functionality
- Changed DELETE /api/events to POST /api/events/delete for better form data compatibility
- Improved HTTP method handling for event deletion API

## [1.0.57] - 2025-09-23

### Fixed
- JSON parsing error in event deletion functionality
- Robust response handling for DELETE /api/events endpoint
- Fallback error messages when API responses are not valid JSON

## [1.0.56] - 2025-09-23

### Added
- Manual event selection and deletion functionality in dashboard
- Checkbox selection for individual events in Recent Events table
- "Select All" and "Delete Selected" buttons for bulk operations
- Confirmation dialog for event deletion with undo warning
- Backend API endpoint DELETE /api/events for bulk event deletion
- Automatic cleanup of associated image files when events are deleted

### Enhanced
- Dashboard UI with improved event management capabilities
- Real-time selection counter showing number of selected events
- Indeterminate checkbox state for partial selections

## [1.0.55] - 2025-09-20

### Removed
- WebSocket references from documentation (feature was never implemented)
- Cleaned up README.md and CHANGELOG.md to reflect current HTTP-only API

## [1.0.54] - 2025-09-20

### Fixed
- Event labeling functionality - "Event not found" error when trying to label events
- Added get_doorbell_event() method to retrieve single event by ID
- Improved event lookup efficiency in label_event endpoint

## [1.0.53] - 2025-09-20

### Fixed
- sqlite3.Row object AttributeError when accessing ai_message field
- Proper column existence check using row.keys() instead of .get() method
- Compatibility with sqlite3.Row objects in database queries

## [1.0.52] - 2025-09-19

### Fixed
- Database migration issue for existing installations without ai_message column
- Backward compatibility with existing doorbell_events table schema
- Added automatic column migration for smooth upgrades

## [1.0.51] - 2025-09-19

### Added
- AI message integration with doorbell events
- Support for AI-generated descriptions from Home Assistant automations
- AI message display in Recent Events dashboard
- Optional ai_message parameter in /api/doorbell/ring endpoint

### Enhanced
- Dashboard now shows AI messages alongside face recognition results
- Backward compatibility maintained for existing integrations
- Database schema extended with ai_message field

## [1.0.50] - 2025-09-19

### Fixed
- Date filter logic in gallery page for proper date range filtering
- "To Date" filter now inclusive instead of exclusive
- Improved date comparison using JavaScript Date objects

## [1.0.49] - 2025-09-19

### Added
- Clickable thumbnail images in Recent Events dashboard
- Image modal popup for viewing full-size event images
- Enhanced user experience with image viewing capabilities

### Fixed
- JavaScript lint errors in dashboard template
- Improved code quality with proper event listeners

## [1.0.48] - 2025-09-17

### Changed
- **BREAKING**: Converted from continuous monitoring to event-driven architecture
- Face recognition now only triggered by doorbell ring events, not continuous capture
- Added new `/api/doorbell/ring` endpoint for doorbell trigger integration
- Removed automatic camera monitoring on startup for better performance and privacy
- Updated documentation with Home Assistant automation setup instructions

### Added
- Event-driven doorbell processing with `/api/doorbell/ring` endpoint
- Webhook notification support for doorbell ring events
- Better resource efficiency - no background camera monitoring

## [1.0.47] - 2025-09-17

### Fixed
- Image serving issue in Home Assistant ingress context
- Changed absolute image paths (/api/images/) to relative paths (api/images/)
- Fixed 404 errors for dashboard and gallery image display

## [1.0.46] - 2025-09-16

### Fixed
- MyPy type checking error in utils.py for PIL ImageFont compatibility
- Added proper Union type annotation for FreeTypeFont | ImageFont
- Fixed import sorting with isort for consistent code formatting

## [1.0.20] - 2024-08-26

### Fixed
- Template loading and import paths for containerized environment
- Settings and gallery page 404 errors resolved
- Corrected absolute file paths (/app/web/templates, /app/web/static)
- Fixed relative imports to use proper module structure (.config, .database, etc.)
- Added database dependency injection to FaceRecognitionManager
- Missing datetime import and ha_camera_manager initialization
- All linting issues resolved (flake8, black, isort, mypy)

## [1.0.14] - 2024-08-22

### Fixed
- Main branch synchronization issue preventing proper version updates
- Corrected workflow to update files → push to main → create tag → push tag

## [1.0.13] - 2024-08-22

### Fixed
- Fixed Docker image name in config.yaml to match actual build output
- Corrected image reference from doorbell-face-recognition to whorang-doorbell-addon

## [1.0.11] - 2024-08-20

### Fixed
- Fixed Docker image name in config.yaml to match actual build output
- Corrected image reference from doorbell-face-recognition to whorang-doorbell-addon

## [1.0.10] - 2024-08-20

### Fixed
- Repository metadata update detached HEAD issue - added ref: main to checkout
- Improved git push logic with proper branch specification
- Better error handling for repository updates

## [1.0.9] - 2024-08-20

### Fixed
- GitHub release creation permissions - switched to GHCR_PAT token
- Repository update permissions - switched to GHCR_PAT token
- Fixed 403 permission errors in release workflow

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
