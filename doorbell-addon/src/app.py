"""Main FastAPI application for the doorbell face recognition addon."""

import os
from datetime import datetime
from typing import Optional

import requests
import structlog
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import settings
from .database import DatabaseManager
from .ha_camera import HACameraManager
from .ha_integration import HomeAssistantIntegration
from .utils import (
    ensure_directories,
    get_storage_usage,
    notification_manager,
    sanitize_filename,
    validate_image_file,
)

# Setup logger first
logger = structlog.get_logger()

# Initialize database
db = DatabaseManager()

# Initialize Home Assistant integration
ha_integration = HomeAssistantIntegration()

# Initialize HA Camera Manager
ha_camera_manager = HACameraManager()

# Face recognition imports
try:
    from .face_recognition import CameraManager, FaceRecognitionManager

    # Initialize face recognition components with proper dependencies
    face_manager = FaceRecognitionManager(db)
    camera_manager = CameraManager(face_manager)

    FACE_RECOGNITION_AVAILABLE = True
    logger.info("Face recognition capabilities loaded successfully")
except ImportError as e:
    face_manager = None
    camera_manager = None
    FACE_RECOGNITION_AVAILABLE = False
    logger.warning(f"Face recognition not available: {e}")

# Initialize FastAPI app
app = FastAPI(
    title="Doorbell Face Recognition",
    description="AI-powered doorbell with face recognition capabilities",
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="/app/web/static"), name="static")
templates = Jinja2Templates(directory="/app/web/templates")


@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    logger.info(
        "Starting Doorbell Face Recognition addon", version=settings.app_version
    )

    # Ensure required directories exist
    ensure_directories()

    # Initialize Home Assistant integration
    await ha_integration.initialize()

    # Start camera monitoring if face recognition is available
    if FACE_RECOGNITION_AVAILABLE and camera_manager:
        camera_manager.start_monitoring()
    else:
        logger.warning("Face recognition not available - camera monitoring disabled")

    logger.info("Addon started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    logger.info("Shutting down Doorbell Face Recognition addon")

    # Stop camera monitoring if available
    if FACE_RECOGNITION_AVAILABLE and camera_manager:
        camera_manager.stop_monitoring()

    # Clean up old events
    db.cleanup_old_events()


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    # Get recent events
    recent_events = db.get_doorbell_events(limit=10)

    # Get persons
    persons = db.get_all_persons()

    # Get storage usage
    storage_info = get_storage_usage()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "recent_events": recent_events,
            "persons": persons,
            "storage_info": storage_info,
            "settings": settings,
        },
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/events")
async def get_events(limit: int = 50, offset: int = 0, person_id: Optional[int] = None):
    """Get doorbell events with pagination."""
    try:
        events = db.get_doorbell_events(
            limit=limit,
            offset=offset,
            person_id=person_id,
        )

        # Convert to dict format
        events_data = []
        for event in events:
            person_name = None
            if event.person_id:
                person = db.get_person(event.person_id)
                person_name = person.name if person else None

            events_data.append(
                {
                    "id": event.id,
                    "timestamp": event.timestamp.isoformat(),
                    "image_path": event.image_path,
                    "person_id": event.person_id,
                    "person_name": person_name,
                    "confidence": event.confidence,
                    "is_known": event.is_known,
                    "processed": event.processed,
                }
            )

        return {"events": events_data}

    except Exception as e:
        logger.error("Error getting events", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/persons")
async def get_persons():
    """Get all persons."""
    try:
        persons = db.get_all_persons()

        persons_data = []
        for person in persons:
            # Get face encoding count
            face_encodings = db.get_face_encodings(person.id)

            persons_data.append(
                {
                    "id": person.id,
                    "name": person.name,
                    "created_at": (
                        person.created_at.isoformat() if person.created_at else None
                    ),
                    "updated_at": (
                        person.updated_at.isoformat() if person.updated_at else None
                    ),
                    "face_count": len(face_encodings),
                }
            )

        return {"persons": persons_data}

    except Exception as e:
        logger.error("Error getting persons", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/persons")
async def create_person(name: str = Form(...)):
    """Create a new person."""
    try:
        # Sanitize name
        name = sanitize_filename(name.strip())

        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")

        person = db.add_person(name)

        return {
            "id": person.id,
            "name": person.name,
            "created_at": person.created_at.isoformat() if person.created_at else None,
        }

    except Exception as e:
        logger.error("Error creating person", name=name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/persons/{person_id}/faces")
async def add_face_to_person(
    person_id: int,
    image: UploadFile = File(...),
    face_x: Optional[int] = Form(None),
    face_y: Optional[int] = Form(None),
    face_width: Optional[int] = Form(None),
    face_height: Optional[int] = Form(None),
):
    """Add a face image to a person."""
    try:
        # Validate person exists
        person = db.get_person(person_id)
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        # Save uploaded image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"upload_{person.name}_{timestamp}_{image.filename}"
        filename = sanitize_filename(filename)
        image_path = os.path.join(settings.images_path, filename)

        with open(image_path, "wb") as f:
            content = await image.read()
            f.write(content)

        # Validate image
        if not validate_image_file(image_path):
            os.remove(image_path)
            raise HTTPException(status_code=400, detail="Invalid image file")

        # Prepare face location if provided
        face_location = None
        if all(v is not None for v in [face_x, face_y, face_width, face_height]):
            # Convert to face_recognition format (top, right, bottom, left)
            face_location = (
                face_y,
                (face_x or 0) + (face_width or 0),
                (face_y or 0) + (face_height or 0),
                face_x or 0,
            )

        # Add face encoding
        success = face_manager.add_face_for_person(
            image_path, person.name, face_location
        )

        if not success:
            os.remove(image_path)
            raise HTTPException(
                status_code=400,
                detail="Could not extract face from image",
            )

        return {
            "message": f"Face added successfully for {person.name}",
            "image_path": image_path,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error adding face to person",
            person_id=person_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/events/{event_id}/label")
async def label_event(event_id: int, person_id: int = Form(...)):
    """Label an event with a person."""
    try:
        # Get event
        events = db.get_doorbell_events(limit=1, offset=0)
        event = None
        for e in events:
            if e.id == event_id:
                event = e
                break

        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        # Get person
        person = db.get_person(person_id)
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        # Process the event image to get face encoding
        if validate_image_file(event.image_path):
            # Add face encoding from this event
            face_manager.add_face_for_person(event.image_path, person.name)

            # Update event
            db.update_event_person(
                event_id, person_id, 0.8
            )  # Default confidence for manual labeling

            # Send notification
            await notification_manager.notify_face_detected(
                person.name, 0.8, event.image_path, is_known=True
            )

        return {"message": f"Event labeled as {person.name}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error labeling event", event_id=event_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/images/{image_name}")
async def get_image(image_name: str):
    """Serve image files."""
    try:
        # Sanitize image name
        image_name = sanitize_filename(image_name)

        # Try images directory first
        image_path = os.path.join(settings.images_path, image_name)
        if os.path.exists(image_path):
            return FileResponse(image_path)

        # Try faces directory
        image_path = os.path.join(settings.faces_path, image_name)
        if os.path.exists(image_path):
            return FileResponse(image_path)

        raise HTTPException(status_code=404, detail="Image not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error serving image", image_name=image_name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/camera/capture")
async def capture_frame():
    """Manually capture a frame from the camera."""
    logger.info("Manual frame capture requested")
    try:
        # Check if camera_manager is available
        if not camera_manager:
            logger.error("Camera manager not initialized")
            raise HTTPException(status_code=500, detail="Camera manager not available")

        # Check camera URL configuration
        camera_url = getattr(camera_manager, "camera_url", None)
        logger.info("Attempting to capture frame", camera_url=camera_url)

        image_path = camera_manager.capture_single_frame()

        if not image_path:
            logger.error("Failed to capture frame - no image path returned")
            raise HTTPException(
                status_code=500, detail="Failed to capture frame from camera"
            )

        logger.info("Frame captured successfully", image_path=image_path)

        # Process the captured frame
        results = face_manager.process_doorbell_image(image_path)
        logger.info("Frame processing completed", results=results)

        return {
            "message": "Frame captured successfully",
            "image_path": os.path.basename(image_path),
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error capturing frame", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Camera capture failed: {str(e)}")


@app.get("/api/settings")
async def get_settings():
    """Get current settings."""
    return {
        "camera_url": settings.camera_url,
        "camera_entity": settings.camera_entity,
        "storage_path": settings.storage_path,
        "retention_days": settings.retention_days,
        "face_confidence_threshold": settings.face_confidence_threshold,
        "notification_webhook": settings.notification_webhook,
        "database_encryption": settings.database_encryption,
        "ha_access_token": settings.ha_access_token,
        "app_version": settings.app_version,
    }


@app.post("/api/settings")
async def update_settings(request: Request):
    """Update settings."""
    try:
        data = await request.json()

        # Update settings and save to file
        if "camera_url" in data:
            settings.camera_url = data["camera_url"]
        if "camera_entity" in data:
            settings.camera_entity = data["camera_entity"]
        if "ha_access_token" in data:
            settings.ha_access_token = data["ha_access_token"]
            logger.info("Home Assistant access token updated via settings")
        if "confidence_threshold" in data:
            settings.face_confidence_threshold = data["confidence_threshold"]

        # Save settings to file for persistence
        settings.save_to_file()
        logger.info(
            "Settings saved to file",
            camera_entity=settings.camera_entity,
            camera_url=settings.camera_url,
        )

        return {"success": True, "message": "Settings updated successfully"}

    except Exception as e:
        logger.error("Error updating settings", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/camera/test")
async def test_camera_connection(request: Request):
    """Test camera connection."""
    try:
        data = await request.json()
        source = data.get("source")
        value = data.get("value")

        if source == "url":
            # Test manual URL connection
            try:
                response = requests.head(value, timeout=5)
                if response.status_code == 200:
                    return {"success": True, "message": "Camera URL is accessible"}
                else:
                    return {
                        "success": False,
                        "error": f"Camera not accessible: {response.status_code}",
                    }
            except Exception as e:
                return {"success": False, "error": str(e)}

        elif source == "entity":
            # Test Home Assistant entity connection
            result = ha_camera_manager.test_camera_connection(value)
            return result

        else:
            return {"success": False, "error": "Invalid source type"}

    except Exception as e:
        logger.error("Error testing camera connection", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cameras")
async def get_available_cameras():
    """Get available Home Assistant camera entities."""
    try:
        logger.info("Camera entities requested via API")
        # Update camera manager with current settings
        ha_camera_manager.supervisor_token = (
            settings.supervisor_token or settings.hassio_token
        )
        ha_camera_manager.ha_access_token = settings.ha_access_token

        cameras = ha_camera_manager.get_available_cameras()
        logger.info(f"Returning {len(cameras)} camera entities")
        return {"cameras": cameras}
    except Exception as e:
        logger.error("Error getting camera entities", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_statistics():
    """Get system statistics."""
    try:
        # Get event counts
        all_events = db.get_doorbell_events(limit=1000)
        total_events = len(all_events)
        known_events = len([e for e in all_events if e.is_known])
        unknown_events = total_events - known_events

        # Get person count
        persons = db.get_all_persons()
        total_persons = len(persons)

        # Get storage usage
        storage_info = get_storage_usage()

        return {
            "total_events": total_events,
            "known_events": known_events,
            "unknown_events": unknown_events,
            "total_persons": total_persons,
            "storage_usage": storage_info,
        }

    except Exception as e:
        logger.error("Error getting statistics", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/gallery", response_class=HTMLResponse)
async def gallery(request: Request):
    """Image gallery page."""
    logger.info("Gallery page requested")
    template_dir = "/app/web/templates"
    logger.debug(f"Templates directory: {template_dir}")

    events = db.get_doorbell_events(limit=100)
    persons = db.get_all_persons()

    try:
        logger.debug("Attempting to render gallery.html template")
        return templates.TemplateResponse(
            "gallery.html",
            {
                "request": request,
                "events": events,
                "persons": persons,
                "settings": settings,
            },
        )
    except Exception as e:
        logger.error(f"Template error for gallery: {e}")
        logger.error(f"Template directory exists: {os.path.exists(template_dir)}")
        logger.error(
            f"Gallery template exists: {os.path.exists(os.path.join(template_dir, 'gallery.html'))}"
        )
        raise HTTPException(status_code=500, detail=f"Template error: {str(e)}")


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page."""
    logger.info("Settings page requested")
    template_dir = "/app/web/templates"
    logger.debug(f"Templates directory: {template_dir}")

    storage_info = get_storage_usage()

    try:
        logger.debug("Attempting to render settings.html template")
        return templates.TemplateResponse(
            "settings.html",
            {"request": request, "settings": settings, "storage_info": storage_info},
        )
    except Exception as e:
        logger.error(f"Template error for settings: {e}")
        logger.error(f"Template directory exists: {os.path.exists(template_dir)}")
        logger.error(
            f"Settings template exists: {os.path.exists(os.path.join(template_dir, 'settings.html'))}"
        )
        raise HTTPException(status_code=500, detail=f"Template error: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8099, log_level="info")
