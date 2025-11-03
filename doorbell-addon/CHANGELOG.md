# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.91] - 2025-11-03

### Fixed
- **STABILITY:** Reverted to proven v1.0.70 behavior - addon always captures from camera
- **DNS Timeout:** Removed /config mapping that was causing addon startup issues
- **Reliability:** External image path feature temporarily disabled for stability

### Changed
- **Camera Capture:** Addon now always captures directly from camera entity/URL
- **External Paths:** image_path parameter accepted but ignored (falls back to camera)
- **Directory Mapping:** Removed config:rw mapping to match stable v1.0.70 configuration

### Technical Details
- Reverted doorbell_ring endpoint to always use camera_manager.capture_single_frame()
- External snapshot feature from v1.0.82 temporarily disabled
- Simplified code path reduces potential failure points
- No file system dependencies beyond /share directory

### Why This Change
v1.0.90 introduced /config directory mapping which caused DNS resolution issues and addon startup failures. This version reverts to the stable, proven behavior from v1.0.70 where everything worked reliably.

### User Impact
- **Guaranteed Stability:** Uses proven code path from v1.0.70
- **Automations Work:** REST command will work reliably
- **Events Appear:** Dashboard will show doorbell events
- **Face Recognition:** All core features functional
- **Trade-off:** External snapshot paths from automations are ignored (addon captures from camera instead)

### Migration Note
Your automation can keep passing image_path parameters - they will be accepted but the addon will capture from the camera instead. This ensures backward compatibility while maintaining stability.

## [1.0.90] - 2025-11-03

### Fixed
- **Critical:** Added `/config` directory mapping to addon configuration
- **REST Command Error:** Addon can now access `/config/www/` snapshots from automations
- **Client Error:** Resolved "Client error occurred" when calling doorbell ring endpoint

### Changed
- **Directory Mapping:** Added `config:rw` to mapped directories in config.yaml
- **File Access:** Addon now has read/write access to Home Assistant config directory

### Technical Details
- Added `/config` mount point to allow access to `/config/www/` directory
- Automation snapshots saved to `/config/www/doorbell_snapshot_*.jpg` are now accessible
- REST command `doorbell_ring` can now process external image paths correctly

### Root Cause
The addon only had access to `/share`, `/ssl`, and `/media` directories. When automations saved snapshots to `/config/www/` and passed the path to the addon, the file couldn't be found because `/config` wasn't mounted in the container.

### User Impact
- **Automations Work:** REST command no longer fails with client errors
- **Events Appear:** Doorbell events now show up in dashboard
- **Face Recognition:** External snapshots from automations are processed correctly
- **No More 404s:** Image paths from automations are now accessible

## [1.0.89] - 2025-10-31

### Changed
- **Documentation:** Replaced technical README with user-friendly setup guide
- **User Experience:** Info tab now shows installation and configuration instructions
- **Technical Docs:** Moved technical documentation to DOCS.md

### Improved
- **First-Time Setup:** Clear step-by-step instructions for new users
- **Quick Start Guide:** Easy-to-follow configuration examples
- **Troubleshooting:** Added common issues and solutions
- **Navigation:** Better organization of user vs. technical documentation

### User Impact
- **Better Onboarding:** New users see helpful setup instructions immediately
- **Reduced Confusion:** Technical details no longer shown by default
- **Quick Reference:** Configuration options clearly explained
- **Easy Access:** Technical docs still available in DOCS.md for developers

### Files Changed
- `doorbell-addon/README.md` - Now user-facing documentation
- `doorbell-addon/DOCS.md` - Technical documentation (renamed from README.md)

## [1.0.88] - 2025-10-31

### Fixed
- **Official HA Compliance:** Now follows official Home Assistant addon publishing guidelines
- **Image Naming:** Corrected to use {arch} placeholder as per HA docs
- **Builder Configuration:** Fixed Home Assistant builder to use explicit arch-specific image names
- **Package Visibility:** Properly sets each architecture package to public

### Changed
- **Build System:** Using Home Assistant builder with correct image naming
- **Image Template:** Added {arch} placeholder in config.yaml and build.yaml
- **Package Names:** Explicitly set to whorang-doorbell-addon-{arch} format
- **CI/CD:** Fixed builder args to create properly named packages

### Technical Implementation
- config.yaml: `image: "ghcr.io/beast12/whorang-doorbell-addon-{arch}"`
- build.yaml: `image: "ghcr.io/beast12/whorang-doorbell-addon-{arch}:1.0.88"`
- Builder args: `--image whorang-doorbell-addon-${{ matrix.arch }}`
- Creates 4 packages: whorang-doorbell-addon-amd64, -aarch64, -armhf, -armv7

### User Impact
- **Follows HA Standards:** Compliant with official Home Assistant documentation
- **Proper Architecture Support:** Each platform gets correct image
- **Automatic Visibility:** Packages automatically set to public after build
- **Works on All Platforms:** amd64, aarch64, armhf, armv7

### Documentation Reference
Following official Home Assistant addon publishing guidelines:
https://developers.home-assistant.io/docs/add-ons/publishing/

The {arch} placeholder is replaced by Home Assistant with the actual architecture when loading the image.

## [1.0.87] - 2025-10-31

### Fixed
- **Package Structure:** Reverted to single multi-arch package instead of separate arch packages
- **Repository Cleanup:** Now uses only `whorang-doorbell-addon` package in Beast12/whorang
- **Image Naming:** Removed architecture-specific package creation

### Changed
- **Build System:** Reverted from Home Assistant builder to Docker buildx
- **Package Strategy:** Single package with multi-arch manifest instead of 4 separate packages
- **Image Reference:** Removed {arch} placeholder from config.yaml

### Technical Implementation
- Restored Docker buildx multi-architecture build
- Single package: `ghcr.io/beast12/whorang-doorbell-addon`
- Multi-arch manifest supports: linux/amd64, linux/arm64, linux/arm/v7
- Docker automatically pulls correct architecture from manifest

### User Impact
- **Cleaner Package Structure:** Only one package to manage
- **Automatic Architecture Selection:** Docker handles architecture detection
- **No More Separate Packages:** Eliminates amd64, arm64, arm/v7 individual packages
- **Correct Repository:** All images in Beast12/whorang repository

### Root Cause
Home Assistant builder creates separate packages per architecture (amd64, arm64, arm/v7), but we need a single package with a multi-architecture manifest. Docker buildx creates the correct structure that Home Assistant can use.

## [1.0.86] - 2025-10-31

### Fixed
- **Docker Image Visibility:** Fixed 403 Forbidden error when pulling images
- **GitHub Packages:** Corrected "Make image public" workflow step
- **Architecture-Specific Packages:** Each arch package now properly set to public

### Changed
- **CI/CD Workflow:** Updated make-public step to use architecture-specific package names
- **Package Naming:** Workflow now targets correct package (e.g., whorang-doorbell-addon-amd64)

### Technical Implementation
- Fixed GitHub API call to use `${{ env.IMAGE_NAME }}-${{ matrix.arch }}`
- Each architecture package (amd64, aarch64, armhf, armv7) now made public separately
- Added error handling to prevent workflow failure if already public

### User Impact
- **Installation Works:** No more 403 Forbidden errors
- **All Architectures:** Images accessible on all platforms
- **Public Packages:** Docker images now properly public on GHCR

### Root Cause
The workflow was trying to make `whorang-doorbell-addon` public, but the actual packages are named `whorang-doorbell-addon-amd64`, `whorang-doorbell-addon-aarch64`, etc. The API call was targeting a non-existent package, leaving all architecture-specific packages private.

## [1.0.85] - 2025-10-30

### Fixed
- **x86/amd64 Architecture:** Fixed "exec format error" on Intel/AMD systems
- **Image Name Template:** Added {arch} placeholder to config.yaml image field
- **Architecture Detection:** Home Assistant now pulls correct architecture-specific image

### Changed
- **config.yaml:** Image name changed from static to architecture-aware template
- **Image Template:** `ghcr.io/beast12/whorang-doorbell-addon` → `ghcr.io/beast12/whorang-doorbell-addon-{arch}`

### Technical Implementation
- Added {arch} placeholder to image field in config.yaml
- Home Assistant substitutes {arch} with actual architecture (amd64, aarch64, armhf, armv7)
- Ensures correct image is pulled for each platform
- Matches image naming pattern from build.yaml

### User Impact
- **x86/amd64 Users:** Addon now starts correctly
- **All Architectures:** Each platform pulls its correct image
- **No More Cross-Architecture Errors:** {arch} template prevents wrong image pulls
- **Universal Fix:** Works on all supported platforms

### Root Cause
The config.yaml had a static image name without {arch} placeholder, causing Home Assistant to pull a random architecture image instead of the platform-specific one. The build.yaml correctly created architecture-specific images (whorang-doorbell-addon-amd64, whorang-doorbell-addon-aarch64, etc.), but config.yaml wasn't telling Home Assistant which one to use.

## [1.0.84] - 2025-10-30

### Fixed
- **ARM 32-bit Build:** Fixed watchfiles Rust compilation error on armhf
- **Dockerfile:** Removed [standard] extras from uvicorn to avoid Rust dependency
- **Build Compatibility:** All architectures now build successfully

### Changed
- **uvicorn Installation:** Changed from `uvicorn[standard]` to `uvicorn` (without extras)
- **Dependency Strategy:** Avoid Rust-dependent packages on ARM 32-bit platforms

### Technical Implementation
- Removed [standard] extras from uvicorn installation
- Prevents watchfiles dependency which requires Rust toolchain
- Rust target arm-unknown-linux-musleabihf not supported by rustup
- Basic uvicorn still provides full ASGI server functionality

### User Impact
- **ARM 32-bit Devices:** Builds now complete successfully
- **Raspberry Pi Users:** No more build failures
- **Functionality:** No impact - uvicorn works the same without [standard] extras
- **Performance:** Minimal difference - [standard] only adds auto-reload features

### Note
The [standard] extras for uvicorn include:
- watchfiles (for auto-reload) - requires Rust
- websockets (for WebSocket support) - not needed
- httptools (for faster parsing) - optional

Basic uvicorn provides all necessary ASGI server functionality for the addon.

## [1.0.83] - 2025-10-30

### Fixed
- **ARM Architecture Build:** Fixed "exec format error" on Raspberry Pi
- **Multi-Architecture Images:** Now builds separate images per architecture
- **Home Assistant Compatibility:** Using HA builder for proper architecture-specific images

### Changed
- **Build System:** Replaced Docker buildx with Home Assistant builder
- **CI/CD Pipeline:** Matrix build strategy for each architecture (amd64, aarch64, armhf, armv7)
- **Image Naming:** Proper architecture-specific image tags

### Technical Implementation
- Switched from docker/build-push-action to home-assistant/builder
- Matrix strategy builds 4 separate images in parallel
- Each architecture gets its own image: {image}-{arch}:{version}
- Proper Home Assistant addon image structure

### User Impact
- **Raspberry Pi Users:** "exec format error" resolved
- **All ARM Devices:** Proper architecture-specific images
- **Faster Installs:** Home Assistant pulls correct image for device
- **No More Errors:** Works on all supported architectures

### Architecture-Specific Images
- ✅ `ghcr.io/beast12/whorang-doorbell-addon-amd64:1.0.83`
- ✅ `ghcr.io/beast12/whorang-doorbell-addon-aarch64:1.0.83`
- ✅ `ghcr.io/beast12/whorang-doorbell-addon-armhf:1.0.83`
- ✅ `ghcr.io/beast12/whorang-doorbell-addon-armv7:1.0.83`

## [1.0.82] - 2025-10-30

### Fixed
- **External Snapshot Support:** Doorbell endpoint now accepts external image parameters
- **Automation Compatibility:** Restored support for Frigate/camera snapshot integration
- **Parameter Validation:** Endpoint no longer rejects ai_title, image_path, image_url parameters

### Added
- **ai_title Parameter:** Accept AI-generated title from automation
- **image_path Parameter:** Accept external snapshot path (e.g., from Frigate)
- **image_url Parameter:** Accept external snapshot URL for reference
- **Fallback Logic:** Use external image if provided, otherwise capture from camera

### Changed
- **Doorbell Ring Endpoint:** Enhanced to support both external snapshots and camera capture
- **Image Source Flexibility:** Can now use pre-captured snapshots from automations
- **Logging:** Added detailed logging for external vs. camera-captured images

### Technical Implementation
- Modified /api/doorbell/ring to accept 4 Form parameters instead of 1
- Added image_path validation and fallback to camera capture
- Preserved backward compatibility - still works without external parameters
- Enhanced logging to track image source (external vs. camera)

### User Impact
- **Existing Automations Work Again:** Automations sending external snapshots now function
- **Frigate Integration:** Can use Frigate snapshots instead of capturing from camera
- **Flexibility:** Choose between external snapshot or camera capture per event
- **No Breaking Changes:** Endpoint still works without any parameters

### Backward Compatibility
- ✅ Works with no parameters (captures from camera)
- ✅ Works with only ai_message (captures from camera)
- ✅ Works with all parameters (uses external snapshot)
- ✅ Falls back to camera if external image doesn't exist

## [1.0.81] - 2025-10-29

### Fixed
- **Raspberry Pi Support:** Added armhf and armv7 architecture support
- **"exec format error":** Resolved architecture mismatch on ARM 32-bit systems
- **Docker Build:** Added linux/arm/v7 platform to GitHub Actions workflow

### Added
- **armhf Architecture:** Support for ARM 32-bit hard float (Raspberry Pi 3/4)
- **armv7 Architecture:** Support for ARM v7 processors
- **Multi-Platform Build:** GitHub Actions now builds for amd64, arm64, and arm/v7

### Changed
- **Architecture Support:** Expanded from 2 to 4 architectures (amd64, aarch64, armhf, armv7)
- **Build Configuration:** Updated build.yaml with armhf and armv7 base images
- **CI/CD Pipeline:** Enhanced to build ARM 32-bit Docker images

### Technical Implementation
- Added armhf and armv7 to config.yaml arch list
- Added armhf and armv7 base images in build.yaml
- Updated GitHub Actions workflow to build linux/arm/v7 platform
- All architectures now use hassio-addons/base:18.1.0

### User Impact
- **Raspberry Pi Users:** Addon now works on all Raspberry Pi models
- **ARM Devices:** Support for 32-bit ARM systems (not just 64-bit)
- **No More Errors:** "exec format error" resolved for ARM 32-bit users
- **Wider Compatibility:** Works on more Home Assistant installations

### Platform Support
- ✅ **amd64** - Intel/AMD 64-bit processors
- ✅ **aarch64** - ARM 64-bit processors
- ✅ **armhf** - ARM 32-bit hard float (Raspberry Pi 3/4)
- ✅ **armv7** - ARM v7 processors

## [1.0.80] - 2025-10-28

### Fixed
- **Data Retention Field:** Removed readonly attribute - now editable
- **Storage Path Field:** Removed readonly attribute - now editable
- **Settings Persistence:** Both fields now save to persistent storage

### Added
- **Save Storage Settings Button:** New button to save retention and storage path changes
- **API Endpoint Support:** POST /api/settings now handles retention_days and storage_path
- **Settings Persistence:** retention_days and storage_path saved to settings.json
- **Input Validation:** Validates retention days (1-365) and storage path (non-empty)
- **Field Descriptions:** Added helpful text under storage path field

### Changed
- **Storage Management UI:** Both input fields now fully editable with save button
- **Settings API:** Enhanced to accept and validate storage configuration
- **Config Persistence:** save_to_file() and load_from_file() include storage settings

### Technical Implementation
- Removed readonly attributes from retention-days and storage-path inputs
- Added saveStorageSettings() JavaScript function with validation
- Enhanced POST /api/settings endpoint with retention_days and storage_path handling
- Added validation: retention_days (1-365), storage_path (non-empty)
- Updated config.py save_to_file() to include retention_days and storage_path
- Updated config.py load_from_file() to restore retention_days and storage_path
- Settings now persist across addon restarts

### User Impact
- Users can now change data retention period through UI
- Users can modify storage path if needed
- Settings persist across addon restarts and Home Assistant reboots
- Clear validation messages for invalid input
- Better control over storage management

## [1.0.79] - 2025-10-28

### Added
- **Storage Cleanup API Endpoint:** POST /api/storage/cleanup for manual data cleanup
- **Storage Info API Endpoint:** GET /api/storage/info for real-time storage usage
- **Functional Cleanup Button:** "Cleanup Old Data" now actually deletes old events
- **Live Storage Refresh:** "Refresh Storage Info" updates without page reload
- **Cleanup Confirmation:** Shows number of events cleaned up after operation

### Fixed
- **Cleanup Old Data Button:** Was showing fake alert, now calls actual API endpoint
- **Refresh Storage Info:** Was just reloading page, now updates dynamically via API
- **Storage Management:** Fully functional manual cleanup based on retention policy

### Changed
- **JavaScript Implementation:** Replaced placeholder functions with real API calls
- **User Feedback:** Better error messages and success notifications for storage operations
- **Storage Display:** Real-time updates to storage usage progress bar and statistics

### Technical Implementation
- Added cleanup_storage() endpoint that counts and removes old events
- Added get_storage_info_api() endpoint for storage statistics
- Enhanced cleanupOldData() JavaScript with proper fetch() API call
- Enhanced refreshStorageInfo() JavaScript with dynamic DOM updates
- Proper error handling and fallback to page reload if API fails

### User Impact
- Storage management features now fully functional
- Users can manually trigger cleanup without waiting for automatic cleanup
- Real-time storage usage updates improve monitoring
- Clear feedback on cleanup operations (number of events removed)

## [1.0.78] - 2025-10-24

### Fixed
- **Test Notification Endpoint:** Fixed 500 Internal Server Error in /api/notifications/test
- **Method Name Mismatch:** Changed send_face_detection_notification() to notify_face_detected() to match actual NotificationManager method

## [1.0.77] - 2025-10-24

### Fixed
- **Test Notifications Button:** Now properly tests notifications via /api/notifications/test endpoint
- **Webhook URL Field:** Removed readonly attribute - users can now edit and save webhook URL
- **Home Assistant Notifications:** Now use proper notify.notify service instead of persistent_notification
- **Notification Fallback:** Added fallback to persistent_notification if notify service fails

### Added
- **Gotify Support:** Automatic detection and proper formatting for Gotify webhook notifications
- **Test Notification Endpoint:** POST /api/notifications/test for testing all notification channels
- **Webhook URL Persistence:** notification_webhook now saved to and loaded from config file
- **Save Webhook Button:** New button in settings to save webhook URL
- **Gotify Format Detection:** Automatically detects Gotify URLs (containing /message) and formats properly

### Changed
- **HA Notification Service:** Changed from persistent_notification/create to notify.notify (standard service)
- **Webhook Notifications:** Enhanced to support both Gotify format and generic webhooks
- **Gotify Payload:** Properly formatted with title, message, priority, and extras containing all event data
- **Settings UI:** Added helpful placeholder text showing Gotify URL format example
- **Config Persistence:** notification_webhook included in save_to_file() and load_from_file()

### Technical Implementation
- Updated HomeAssistantAPI.send_notification() to use notify.notify service with fallback
- Enhanced _send_webhook_notification() with Gotify detection and formatting
- Added notification_webhook to config.py persistence methods
- Created /api/notifications/test endpoint in app.py
- Updated settings.html with saveWebhookUrl() JavaScript function
- Added notification_webhook to /api/settings POST endpoint

### User Impact
- Users can now properly configure and test notifications from settings page
- Gotify users receive properly formatted notifications with all metadata
- Home Assistant notifications work with all notification platforms (mobile_app, telegram, etc.)
- Test button actually sends test notifications to verify setup is working
- Webhook URL persists across addon restarts

## [1.0.76] - 2025-10-24

### Fixed
- **404 Error on View Events Button:** Fixed People Management "View Events" button returning 404 error
- **URL Routing Issue:** Changed from absolute URL path (`/gallery?person=X`) to relative path (`gallery?person=X`)
- **Home Assistant Ingress Compatibility:** View Events now works correctly through HA ingress proxy

### Changed
- **Accurate Documentation:** Removed inaccurate "AI-powered" claims throughout documentation
- **ML-Based Description:** Changed to "Face recognition doorbell add-on with ML-based detection"
- **AI Feature Clarification:** Clarified that AI descriptions come from external integrations (LLM Vision), not generated by addon

### Added
- **GitHub Actions Badge:** Added build status badge to main README
- **Screenshots Section:** Added dashboard, gallery, and settings screenshots to README
- **Configuration Clarity:** Improved configuration documentation showing camera_entity OR camera_url options

### Documentation
- Updated all descriptions from "AI-powered" to "ML-based face recognition"
- Fixed configuration examples to accurately reflect either/or camera options
- Added note explaining difference between camera_entity and camera_url usage
- Verified all documentation against actual source code

## [1.0.75] - 2025-10-24

### Changed
- **Documentation Consolidation:** Completely restructured all documentation for clarity and professionalism
- **Main README:** Root README.md is now the primary documentation with complete setup instructions
- **Technical README:** Addon README.md now focuses on technical details and API reference
- **Automation Guide:** Created separate AUTOMATION.md with detailed automation examples
- **Removed Clutter:** Deleted outdated version references and redundant documentation
- **Removed Files:** Deleted private-repo-setup.md (no longer needed)

### Improved
- **Professional Structure:** Clear separation between user docs and technical docs
- **Version Consistency:** All documentation now references current version (1.0.75)
- **Navigation:** Added clear links between documentation files
- **User Experience:** Main README provides complete setup without jumping between files
- **Developer Experience:** Technical details consolidated in addon README

### Fixed
- **Outdated Changelog:** Removed old changelog entries from addon README (stopped at v1.0.20)
- **Duplicate Content:** Eliminated redundant information between root and addon READMEs
- **Confusing Structure:** Clear hierarchy - root README for users, addon README for developers
- **Version References:** Updated all version badges and references to 1.0.75

### User Impact
- Users now have one clear place to start (root README.md)
- Complete setup instructions without jumping between files
- Technical users can dive into addon README for API details
- Professional, organized documentation structure

## [1.0.74] - 2025-10-24

### Added
- **Comprehensive Setup Documentation:** Complete step-by-step integration guide in README
- **REST Command Configuration:** Clear instructions for adding doorbell_ring REST command
- **Two Automation Options:** Simple and advanced automation examples with placeholders
- **Placeholder Replacement Guide:** Helpful table showing how to find and replace all entities
- **Troubleshooting Section:** Common issues and solutions for integration setup
- **Support Section:** Added Buy Me a Coffee support links and QR code

### Improved
- **User-Friendly Documentation:** Restructured README for non-technical users
- **Clear Step Numbering:** Easy-to-follow numbered steps for setup process
- **Inline Comments:** Added explanatory comments to automation examples
- **Entity Discovery Guide:** Instructions on how to find device IDs, entities, and URLs

### Technical
- Removed all personal data from automation examples
- Used generic placeholders for all user-specific configuration
- Added note about addon slug varying between installations
- Included proper REST command timeout configuration

### User Impact
- Non-technical users can now easily set up the addon
- Clear path from installation to working face recognition
- Reduced support requests with comprehensive troubleshooting
- Community can support development via Buy Me a Coffee

## [1.0.73] - 2025-10-24

### Fixed
- **People Page 500 Error:** Fixed Internal Server Error when accessing /people page
- **Template Context:** Added missing settings object to people page template context
- Base template requires settings.app_version for footer display

### Technical
- Updated people_page() route to include settings in template context
- Ensures all pages have consistent template variables
- Prevents template rendering errors from missing context variables

### User Impact
- People management page now loads correctly without 500 errors
- Can access and manage registered people through the web interface
- Consistent footer display across all pages

## [1.0.72] - 2025-10-24

### Fixed
- **Dashboard Card Navigation:** Fixed 404 errors when clicking dashboard cards in Home Assistant ingress
- **Ingress Compatibility:** Changed card onclick URLs from absolute paths to relative paths
- All dashboard cards now properly navigate through Home Assistant ingress proxy

### Technical
- Updated dashboard.html card onclick handlers to use relative URLs (gallery, people) instead of absolute (/gallery, /people)
- Ensures proper URL resolution in Home Assistant ingress environment
- Maintains compatibility with both direct access and ingress proxy

### User Impact
- Dashboard cards now work correctly when accessed through Home Assistant
- No more 404 errors when clicking Total Events, Known Faces, Unknown Faces, or Registered People cards
- Seamless navigation experience in ingress environment

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
- ML-based face recognition using face_recognition library
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
