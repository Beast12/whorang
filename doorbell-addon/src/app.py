"""Main FastAPI application for the doorbell face recognition addon."""

import os
from datetime import datetime
from typing import Optional

import structlog
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import settings
from .database import db
from .ha_camera import ha_camera_manager
from .ha_integration import ha_integration
from .utils import (
    ensure_directories,
    get_storage_usage,
    notification_manager,
    sanitize_filename,
    validate_image_file,
)

# Setup logger first
logger = structlog.get_logger()

# Face recognition imports
try:
    from .face_recognition import camera_manager, face_manager

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
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")


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
    try:
        image_path = camera_manager.capture_single_frame()

        if not image_path:
            raise HTTPException(status_code=500, detail="Failed to capture frame")

        # Process the captured frame
        results = face_manager.process_doorbell_image(image_path)

        return {
            "message": "Frame captured successfully",
            "image_path": os.path.basename(image_path),
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error capturing frame", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/settings")
async def get_settings():
    """Get current settings."""
    return {
        "camera_url": settings.camera_url,
        "storage_path": settings.storage_path,
        "retention_days": settings.retention_days,
        "face_confidence_threshold": settings.face_confidence_threshold,
        "notification_webhook": settings.notification_webhook,
        "database_encryption": settings.database_encryption,
        "app_version": settings.app_version,
    }


@app.post("/api/settings")
async def update_settings(request: Request):
    """Update settings."""
    try:
        data = await request.json()

        # Update settings (in a real implementation, you'd save to config file)
        if "camera_url" in data:
            settings.camera_url = data["camera_url"]
        if "camera_entity" in data:
            # Handle camera entity selection
            pass
        if "confidence_threshold" in data:
            settings.face_confidence_threshold = data["confidence_threshold"]

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
            # Test direct URL connection
            import cv2

            cap = cv2.VideoCapture(value)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret:
                    return {"success": True, "message": "Camera connection successful"}
                else:
                    return {"success": False, "error": "Could not read from camera"}
            else:
                return {"success": False, "error": "Could not connect to camera"}

        elif source == "entity":
            # Test Home Assistant camera entity
            result = ha_camera_manager.test_camera_connection(value)
            return result

        else:
            return {"success": False, "error": "Invalid camera source"}

    except Exception as e:
        logger.error("Error testing camera", error=str(e))
        return {"success": False, "error": str(e)}


@app.get("/api/cameras")
async def get_cameras():
    """Get available Home Assistant camera entities."""
    try:
        cameras = ha_camera_manager.get_available_cameras()
        return {"cameras": cameras}
    except Exception as e:
        logger.error("Error getting cameras", error=str(e))
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
    events = db.get_doorbell_events(limit=100)
    persons = db.get_all_persons()

    return templates.TemplateResponse(
        "gallery.html", {"request": request, "events": events, "persons": persons}
    )


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page."""
    storage_info = get_storage_usage()

    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "settings": settings, "storage_info": storage_info},
    )


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8099, log_level="info")
