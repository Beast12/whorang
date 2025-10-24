"""Main FastAPI application for the doorbell face recognition addon."""

import os
import sqlite3
from datetime import datetime
from typing import Optional

import httpx
import requests
import structlog
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .database import DatabaseManager
from .ha_camera import HACameraManager
from .ha_integration import HomeAssistantIntegration
from .utils import (
    HomeAssistantAPI,
    create_placeholder_image,
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


class IngressAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to handle Home Assistant ingress authentication."""

    async def dispatch(self, request: Request, call_next):
        # Skip middleware for API documentation routes and their static assets
        api_docs_paths = (
            "/api/docs",
            "/api/redoc",
            "/api/openapi.json",
            "/docs",
            "/redoc",
            "/openapi.json",
        )
        if (
            request.url.path.startswith(api_docs_paths)
            or request.url.path in api_docs_paths
        ):
            return await call_next(request)

        # For ingress, we need to trust the proxy headers
        # Home Assistant ingress handles authentication at the proxy level

        # Get the original request headers
        headers = dict(request.headers)

        # Log ingress headers for debugging
        ingress_headers = {
            k: v
            for k, v in headers.items()
            if "ingress" in k.lower() or "x-" in k.lower()
        }
        if ingress_headers:
            logger.debug("Ingress headers received", headers=ingress_headers)

        # Check for Home Assistant ingress session headers
        has_ingress_session = (
            "x-ingress-path" in headers
            or "x-hassio-key" in headers
            or "authorization" in headers
            or request.url.path.startswith("/api/hassio_ingress/")
        )

        if has_ingress_session:
            logger.debug("Request has ingress session", path=request.url.path)

        # Process the request
        response = await call_next(request)

        # Add CORS headers for ingress compatibility
        if has_ingress_session:
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, DELETE, OPTIONS"
            )
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Access-Control-Allow-Credentials"] = "true"

        return response


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
    title="Doorbell Face Recognition API",
    description=(
        "AI-powered doorbell with face recognition capabilities. "
        "This API provides endpoints for managing doorbell events, "
        "face recognition, weather integration, and system configuration."
    ),
    version=settings.app_version,
    docs_url=None,  # Disable automatic docs
    redoc_url=None,  # Disable automatic redoc
    openapi_url="/openapi.json",
)

# Add ingress authentication middleware
app.add_middleware(IngressAuthMiddleware)

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

    # Don't start continuous monitoring - doorbell events are trigger-based
    # Camera monitoring will be triggered by doorbell ring events via /api/doorbell/ring
    logger.info("Doorbell addon ready - waiting for doorbell ring events")

    logger.info("Addon started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    logger.info("Shutting down Doorbell Face Recognition addon")

    # No continuous monitoring to stop - doorbell is event-driven

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


@app.options("/{full_path:path}")
async def options_handler(request: Request, full_path: str):
    """Handle OPTIONS preflight requests for CORS."""
    return {"message": "OK"}


@app.get("/api/events", tags=["Events"], summary="Get doorbell events")
async def get_events(limit: int = 50, offset: int = 0, person_id: Optional[int] = None):
    """
    Get doorbell events with pagination and optional filtering.

    - **limit**: Maximum number of events to return (default: 50)
    - **offset**: Number of events to skip for pagination (default: 0)
    - **person_id**: Filter events by specific person ID (optional)

    Returns a list of doorbell events with face recognition results, weather data, and AI messages.
    """
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


@app.get("/api/persons", tags=["Persons"], summary="Get all persons")
async def get_persons():
    """
    Get all registered persons in the face recognition system.

    Returns a list of all persons with their IDs, names, and face count.
    """
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

        return persons_data

    except Exception as e:
        logger.error("Error getting persons", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/persons", tags=["Persons"], summary="Create a new person")
async def create_person(name: str = Form(...)):
    """
    Create a new person in the face recognition system.

    - **name**: The name of the person to create

    Returns the created person with their assigned ID.
    """
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

    except sqlite3.IntegrityError as e:
        logger.error("Person already exists", name=name, error=str(e))
        raise HTTPException(
            status_code=400,
            detail=f"A person with the name '{name}' already exists. Please use a different name.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating person", name=name, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to create person: {str(e)}"
        )


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


@app.put("/api/persons/{person_id}")
async def update_person(person_id: int, name: str = Form(...)):
    """Update a person's name."""
    try:
        person = db.get_person(person_id)
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        # Sanitize name
        name = sanitize_filename(name.strip())
        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")

        # Update person name in database
        db.update_person_name(person_id, name)

        return {
            "message": f"Person updated successfully",
            "id": person_id,
            "name": name,
        }

    except sqlite3.IntegrityError as e:
        logger.error("Person name already exists", name=name, error=str(e))
        raise HTTPException(
            status_code=400,
            detail=f"A person with the name '{name}' already exists. Please use a different name.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating person", person_id=person_id, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to update person: {str(e)}"
        )


@app.delete("/api/persons/{person_id}")
async def delete_person(person_id: int):
    """Delete a person and all their face encodings."""
    try:
        person = db.get_person(person_id)
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        # Delete person from database (cascade will delete face encodings)
        db.delete_person(person_id)

        return {"message": f"Person '{person.name}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting person", person_id=person_id, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to delete person: {str(e)}"
        )


@app.post("/api/events/delete")
async def delete_events(event_ids: str = Form(...)):
    """Delete multiple events by their IDs."""
    try:
        # Parse comma-separated event IDs
        ids = [int(id.strip()) for id in event_ids.split(",") if id.strip()]

        if not ids:
            raise HTTPException(status_code=400, detail="No event IDs provided")

        # Delete events
        deleted_count = db.delete_events(ids)

        return {
            "message": f"Successfully deleted {deleted_count} event(s)",
            "deleted_count": deleted_count,
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid event ID format")
    except Exception as e:
        logger.error("Error deleting events", event_ids=event_ids, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/events/{event_id}/label")
async def label_event(event_id: int, person_id: int = Form(...)):
    """Label an event with a person."""
    try:
        # Get event by ID
        event = db.get_doorbell_event(event_id)

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
        logger.debug(f"Serving image: {image_name}")

        # Try images directory first
        image_path = os.path.join(settings.images_path, image_name)
        logger.debug(f"Checking images path: {image_path}")
        if os.path.exists(image_path):
            logger.debug(f"Found image at: {image_path}")
            return FileResponse(image_path)

        # Try faces directory
        image_path = os.path.join(settings.faces_path, image_name)
        logger.debug(f"Checking faces path: {image_path}")
        if os.path.exists(image_path):
            logger.debug(f"Found image at: {image_path}")
            return FileResponse(image_path)

        # Create placeholder image if not found
        logger.warning(f"Image not found: {image_name}, creating placeholder")
        placeholder_path = create_placeholder_image(image_name)
        if placeholder_path and os.path.exists(placeholder_path):
            return FileResponse(placeholder_path)

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
            raise HTTPException(status_code=503, detail="Camera manager not available")

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
        results = await face_manager.process_doorbell_image(image_path)
        logger.info("Frame processing completed", results=results)

        return {
            "success": True,
            "message": "Frame captured and processed successfully",
            "image_path": image_path,
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error during frame capture", error=str(e))
        raise HTTPException(status_code=500, detail=f"Capture failed: {str(e)}")


@app.post("/api/doorbell/ring", tags=["Events"], summary="Handle doorbell ring event")
async def doorbell_ring(ai_message: Optional[str] = Form(None)):
    """
    Handle a doorbell ring event - capture frame and process for face recognition.

    - **ai_message**: Optional AI-generated message about the event

    This endpoint captures a frame from the doorbell camera, processes it for face recognition,
    captures weather data, and stores the event in the database.
    """
    logger.info("Doorbell ring event received")
    try:
        # Check if camera_manager is available
        if not camera_manager:
            raise HTTPException(status_code=503, detail="Camera manager not available")

        # Capture frame from doorbell camera
        image_path = camera_manager.capture_single_frame()

        if not image_path:
            logger.error("Failed to capture frame from doorbell")
            raise HTTPException(
                status_code=500, detail="Failed to capture frame from doorbell camera"
            )

        logger.info("Doorbell frame captured successfully", image_path=image_path)

        # Process the captured frame for face recognition
        results = await face_manager.process_doorbell_image(image_path, ai_message)
        logger.info(
            "Doorbell frame processing completed",
            results=results,
            ai_message=ai_message,
        )

        # Send notification if configured
        if settings.notification_webhook:
            try:
                import requests

                notification_data = {
                    "event": "doorbell_ring",
                    "timestamp": results["timestamp"].isoformat(),
                    "faces_detected": results["faces_detected"],
                    "known_faces": results["known_faces"],
                    "image_path": image_path,
                }
                requests.post(
                    settings.notification_webhook, json=notification_data, timeout=5
                )
            except Exception as e:
                logger.warning("Failed to send notification", error=str(e))

        return {
            "success": True,
            "message": "Doorbell ring processed successfully",
            "event_id": results["event_id"],
            "faces_detected": results["faces_detected"],
            "known_faces": results["known_faces"],
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error processing doorbell ring", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Doorbell processing failed: {str(e)}"
        )


@app.get("/api/settings", tags=["Settings"], summary="Get current settings")
async def get_settings():
    """
    Get current addon configuration settings.

    Returns all configurable settings including camera, weather, and face recognition parameters.
    """
    return {
        "camera_url": settings.camera_url,
        "camera_entity": settings.camera_entity,
        "storage_path": settings.storage_path,
        "retention_days": settings.retention_days,
        "face_confidence_threshold": settings.face_confidence_threshold,
        "notification_webhook": settings.notification_webhook,
        "weather_entity": settings.weather_entity,
        "database_encryption": settings.database_encryption,
        "ha_access_token": settings.ha_access_token,
        "app_version": settings.app_version,
    }


@app.post("/api/settings", tags=["Settings"], summary="Update settings")
async def update_settings(request: Request):
    """
    Update addon configuration settings.

    Accepts a JSON payload with settings to update. Settings are automatically saved to persistent storage.
    """
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
        if "weather_entity" in data:
            settings.weather_entity = data["weather_entity"]
            logger.info(
                "Weather entity updated via settings",
                weather_entity=settings.weather_entity,
            )
        if "notification_webhook" in data:
            settings.notification_webhook = data["notification_webhook"]
            logger.info("Notification webhook updated via settings")

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


@app.post("/api/notifications/test", tags=["Notifications"], summary="Test notifications")
async def test_notifications():
    """
    Test notification system by sending a test notification to Home Assistant and webhook.
    
    This endpoint sends a test notification through all configured notification channels:
    - Home Assistant notify service
    - External webhook (if configured)
    """
    try:
        from .utils import notification_manager
        
        # Send test notification
        await notification_manager.send_face_detection_notification(
            person_name="Test User",
            confidence=0.95,
            is_known=True,
            image_path="/test/image.jpg"
        )
        
        return {
            "success": True,
            "message": "Test notifications sent successfully! Check your Home Assistant notifications and webhook."
        }
    except Exception as e:
        logger.error("Error sending test notification", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to send test notification: {str(e)}")


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


@app.get("/api/cameras", tags=["Camera"], summary="Get available camera entities")
async def get_available_cameras():
    """
    Get available Home Assistant camera entities for doorbell integration.

    Returns a list of camera entities that can be used as doorbell camera sources.
    """
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


@app.get(
    "/api/weather-entities", tags=["Weather"], summary="Get available weather entities"
)
async def get_available_weather_entities():
    """
    Get available Home Assistant weather entities for integration.

    Returns a list of weather entities that can be used to capture weather conditions with doorbell events.
    """
    try:
        logger.info("Weather entities requested via API")

        # Use the Home Assistant API to get weather entities
        ha_api = HomeAssistantAPI()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ha_api.base_url}/states",
                headers=ha_api.headers,
            )
            response.raise_for_status()
            states = response.json()

            # Filter for weather entities
            weather_entities = []
            for state in states:
                entity_id = state.get("entity_id", "")
                if entity_id.startswith("weather."):
                    attributes = state.get("attributes", {})
                    friendly_name = attributes.get("friendly_name", entity_id)
                    weather_entities.append(
                        {
                            "entity_id": entity_id,
                            "friendly_name": friendly_name,
                            "state": state.get("state"),
                        }
                    )

            logger.info(f"Returning {len(weather_entities)} weather entities")
            return {"entities": weather_entities}

    except Exception as e:
        logger.error("Error getting weather entities", error=str(e))
        return {"entities": []}


@app.get("/api/stats", tags=["System"], summary="Get system statistics")
async def get_statistics():
    """
    Get system statistics and usage information.

    Returns statistics about events, storage usage, and system performance.
    """
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


@app.api_route(
    "/docs",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    response_class=HTMLResponse,
)
async def api_documentation():
    """Simple API documentation page that actually works."""
    return HTMLResponse(
        """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Doorbell Face Recognition API Documentation</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
            h2 { color: #34495e; margin-top: 30px; }
            .endpoint { background: #ecf0f1; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #3498db; }
            .method { display: inline-block; padding: 4px 8px; border-radius: 3px; color: white; font-weight: bold; margin-right: 10px; }
            .get { background: #27ae60; }
            .post { background: #e74c3c; }
            .put { background: #f39c12; }
            .delete { background: #e67e22; }
            code { background: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-family: 'Courier New', monospace; }
            .description { margin-top: 8px; color: #7f8c8d; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚪 Doorbell Face Recognition API</h1>
            <p>AI-powered doorbell with face recognition capabilities. This API provides endpoints for managing doorbell events, face recognition, weather integration, and system configuration.</p>
            
            <h2>📊 System Endpoints</h2>
            <div class="endpoint">
                <span class="method get">GET</span><code>/health</code>
                <div class="description">Health check endpoint for monitoring system status</div>
            </div>
            <div class="endpoint">
                <span class="method get">GET</span><code>/api/stats</code>
                <div class="description">Get system statistics including event counts and storage usage</div>
            </div>
            
            <h2>🎯 Event Management</h2>
            <div class="endpoint">
                <span class="method get">GET</span><code>/api/events</code>
                <div class="description">Get doorbell events with pagination. Parameters: limit, offset, person_id</div>
            </div>
            <div class="endpoint">
                <span class="method post">POST</span><code>/api/doorbell/ring</code>
                <div class="description">Handle doorbell ring event - capture frame and process for face recognition</div>
            </div>
            <div class="endpoint">
                <span class="method post">POST</span><code>/api/events/{event_id}/label</code>
                <div class="description">Label an event with a person ID</div>
            </div>
            <div class="endpoint">
                <span class="method post">POST</span><code>/api/events/delete</code>
                <div class="description">Delete multiple events by their IDs</div>
            </div>
            
            <h2>👥 Person Management</h2>
            <div class="endpoint">
                <span class="method get">GET</span><code>/api/persons</code>
                <div class="description">Get all registered persons in the face recognition system</div>
            </div>
            <div class="endpoint">
                <span class="method post">POST</span><code>/api/persons</code>
                <div class="description">Create a new person. Form data: name</div>
            </div>
            <div class="endpoint">
                <span class="method post">POST</span><code>/api/persons/{person_id}/faces</code>
                <div class="description">Add face image to a person. Form data: image file</div>
            </div>
            
            <h2>⚙️ Settings & Configuration</h2>
            <div class="endpoint">
                <span class="method get">GET</span><code>/api/settings</code>
                <div class="description">Get current addon configuration settings</div>
            </div>
            <div class="endpoint">
                <span class="method post">POST</span><code>/api/settings</code>
                <div class="description">Update addon settings. JSON payload with configuration options</div>
            </div>
            <div class="endpoint">
                <span class="method get">GET</span><code>/api/cameras</code>
                <div class="description">Get available Home Assistant camera entities</div>
            </div>
            <div class="endpoint">
                <span class="method post">POST</span><code>/api/camera/test</code>
                <div class="description">Test camera connection</div>
            </div>
            <div class="endpoint">
                <span class="method post">POST</span><code>/api/camera/capture</code>
                <div class="description">Manually capture a frame from the camera</div>
            </div>
            
            <h2>🌤️ Weather Integration</h2>
            <div class="endpoint">
                <span class="method get">GET</span><code>/api/weather-entities</code>
                <div class="description">Get available Home Assistant weather entities for integration</div>
            </div>
            
            <h2>🖼️ Image Access</h2>
            <div class="endpoint">
                <span class="method get">GET</span><code>/api/images/{image_name}</code>
                <div class="description">Serve image files from the doorbell events</div>
            </div>
            
            <h2>📱 Web Interface</h2>
            <div class="endpoint">
                <span class="method get">GET</span><code>/</code>
                <div class="description">Main dashboard page with recent events</div>
            </div>
            <div class="endpoint">
                <span class="method get">GET</span><code>/gallery</code>
                <div class="description">Image gallery page with event filtering</div>
            </div>
            <div class="endpoint">
                <span class="method get">GET</span><code>/settings</code>
                <div class="description">Settings configuration page</div>
            </div>
            
            <p style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ecf0f1; color: #7f8c8d;">
                <strong>Version:</strong> 1.0.67 | 
                <strong>Base URL:</strong> Your Home Assistant addon URL | 
                <strong>Authentication:</strong> Handled by Home Assistant ingress
            </p>
        </div>
    </body>
    </html>
    """
    )


@app.get("/api-docs", response_class=HTMLResponse)
async def api_docs_redirect():
    """Redirect to API documentation."""
    return HTMLResponse(
        """
    <!DOCTYPE html>
    <html>
    <head>
        <title>API Documentation - Doorbell Face Recognition</title>
        <meta http-equiv="refresh" content="0; url=/docs">
    </head>
    <body>
        <p>Redirecting to API documentation...</p>
        <p>If you are not redirected automatically, <a href="/docs">click here</a>.</p>
    </body>
    </html>
    """
    )


@app.get("/people", response_class=HTMLResponse)
async def people_page(request: Request):
    """People management page."""
    logger.info("People page requested")

    try:
        persons = db.get_all_persons()
        return templates.TemplateResponse(
            "people.html",
            {"request": request, "persons": persons, "settings": settings},
        )
    except Exception as e:
        logger.error(f"Template error for people: {e}")
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
