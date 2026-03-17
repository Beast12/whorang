"""Main FastAPI application for the WhoRang doorbell addon."""

import asyncio
import json
import os
from datetime import datetime
from typing import Any, List, Optional

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
from .database import db
from .face_recognition_service import face_recognition_service
from .ha_camera import ha_camera_manager
from .ha_integration import ha_integration
from .utils import (
    HomeAssistantAPI,
    create_placeholder_image,
    ensure_directories,
    get_storage_usage,
    notification_manager,
    sanitize_filename,
)

logger = structlog.get_logger()


class IngressAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to handle Home Assistant ingress authentication."""

    async def dispatch(self, request: Request, call_next):
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

        headers = dict(request.headers)
        ingress_headers = {
            k: v
            for k, v in headers.items()
            if "ingress" in k.lower() or "x-" in k.lower()
        }
        if ingress_headers:
            logger.debug("Ingress headers received", headers=ingress_headers)

        has_ingress_session = (
            "x-ingress-path" in headers
            or "x-hassio-key" in headers
            or "authorization" in headers
            or request.url.path.startswith("/api/hassio_ingress/")
        )

        response = await call_next(request)

        if has_ingress_session:
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, DELETE, OPTIONS"
            )
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Access-Control-Allow-Credentials"] = "true"

        return response


app = FastAPI(
    title="WhoRang Doorbell API",
    description="Doorbell event history with image capture and weather integration.",
    version=settings.app_version,
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
)

app.add_middleware(IngressAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="/app/web/static"), name="static")
templates = Jinja2Templates(directory="/app/web/templates")
templates.env.filters["fromjson"] = lambda s: json.loads(s) if s else []


@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    logger.info("Starting WhoRang doorbell addon", version=settings.app_version)
    ensure_directories()
    await ha_integration.initialize()
    if settings.face_recognition_enabled:
        asyncio.create_task(face_recognition_service.initialize())
    logger.info("WhoRang addon ready - waiting for doorbell ring events")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    logger.info("Shutting down WhoRang doorbell addon")
    db.cleanup_old_events()


# ── Web pages ────────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    recent_events = db.get_doorbell_events(limit=10)
    storage_info = get_storage_usage()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "recent_events": recent_events,
            "storage_info": storage_info,
            "settings": settings,
        },
    )


@app.get("/gallery", response_class=HTMLResponse)
async def gallery(request: Request):
    """Image gallery page."""
    events = db.get_doorbell_events(limit=100)

    return templates.TemplateResponse(
        "gallery.html",
        {
            "request": request,
            "events": events,
            "settings": settings,
        },
    )


@app.get("/persons", response_class=HTMLResponse)
async def persons_page(request: Request):
    """Known persons page."""
    persons = db.get_persons()
    return templates.TemplateResponse(
        "persons.html",
        {"request": request, "persons": persons, "settings": settings},
    )


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page."""
    storage_info = get_storage_usage()

    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "settings": settings, "storage_info": storage_info},
    )


@app.api_route(
    "/docs",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    response_class=HTMLResponse,
)
async def api_documentation():
    """API documentation page."""
    return HTMLResponse(
        """<!DOCTYPE html>
<html>
<head>
    <title>WhoRang API Documentation</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px;
                     border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        h2 { color: #34495e; margin-top: 30px; }
        .endpoint { background: #ecf0f1; padding: 15px; margin: 10px 0; border-radius: 5px;
                    border-left: 4px solid #3498db; }
        .method { display: inline-block; padding: 4px 8px; border-radius: 3px; color: white;
                  font-weight: bold; margin-right: 10px; }
        .get { background: #27ae60; }
        .post { background: #e74c3c; }
        code { background: #f8f9fa; padding: 2px 6px; border-radius: 3px; }
        .description { margin-top: 8px; color: #7f8c8d; }
    </style>
</head>
<body>
<div class="container">
    <h1>🚪 WhoRang Doorbell API</h1>

    <h2>System</h2>
    <div class="endpoint">
        <span class="method get">GET</span><code>/health</code>
        <div class="description">Health check</div>
    </div>
    <div class="endpoint">
        <span class="method get">GET</span><code>/api/stats</code>
        <div class="description">System statistics</div>
    </div>

    <h2>Events</h2>
    <div class="endpoint">
        <span class="method get">GET</span><code>/api/events?limit=50&amp;offset=0</code>
        <div class="description">Get doorbell events with pagination</div>
    </div>
    <div class="endpoint">
        <span class="method post">POST</span><code>/api/doorbell/ring</code>
        <div class="description">Trigger doorbell ring — captures image, records event. Form: ai_message (optional)</div>
    </div>
    <div class="endpoint">
        <span class="method post">POST</span><code>/api/events/{event_id}/comment</code>
        <div class="description">Add or update comment on an event. Form: comment</div>
    </div>
    <div class="endpoint">
        <span class="method post">POST</span><code>/api/events/delete</code>
        <div class="description">Delete events. Form: event_ids (comma-separated)</div>
    </div>

    <h2>Settings &amp; Camera</h2>
    <div class="endpoint">
        <span class="method get">GET</span><code>/api/settings</code>
        <div class="description">Get current settings</div>
    </div>
    <div class="endpoint">
        <span class="method post">POST</span><code>/api/settings</code>
        <div class="description">Update settings (JSON body)</div>
    </div>
    <div class="endpoint">
        <span class="method get">GET</span><code>/api/cameras</code>
        <div class="description">List available HA camera entities</div>
    </div>
    <div class="endpoint">
        <span class="method post">POST</span><code>/api/camera/test</code>
        <div class="description">Test camera connection. JSON: {source, value}</div>
    </div>
    <div class="endpoint">
        <span class="method get">GET</span><code>/api/weather-entities</code>
        <div class="description">List available HA weather entities</div>
    </div>
    <div class="endpoint">
        <span class="method get">GET</span><code>/api/images/{image_name}</code>
        <div class="description">Serve event image files</div>
    </div>
</div>
</body>
</html>"""
    )


# ── System ────────────────────────────────────────────────────────────────────


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


@app.get("/api/stats")
async def get_statistics():
    """Get system statistics."""
    try:
        total_events, storage_info = await asyncio.gather(
            asyncio.to_thread(db.get_event_count),
            asyncio.to_thread(get_storage_usage),
        )
        return {
            "total_events": total_events,
            "storage_usage": storage_info,
        }
    except Exception as e:
        logger.error("Error getting statistics", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ── Events ────────────────────────────────────────────────────────────────────


@app.get("/api/events")
async def get_events(limit: int = 50, offset: int = 0):
    """Get doorbell events with pagination."""
    try:
        events = db.get_doorbell_events(limit=limit, offset=offset)

        events_data = [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat(),
                "image_path": e.image_path,
                "ai_message": e.ai_message,
                "weather_condition": e.weather_condition,
                "weather_temperature": e.weather_temperature,
                "weather_humidity": e.weather_humidity,
                "faces_detected": e.faces_detected,
                "face_data": json.loads(e.face_data) if e.face_data else [],
            }
            for e in events
        ]

        return {"events": events_data}

    except Exception as e:
        logger.error("Error getting events", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/doorbell/ring")
async def doorbell_ring(
    ai_message: Optional[str] = Form(None),
    image_path: Optional[str] = Form(None),
):
    """Handle a doorbell ring event — capture image and record the event."""
    logger.info("Doorbell ring event received", ai_message=ai_message)
    try:
        # If a pre-captured snapshot path is provided (e.g. from the HA automation),
        # copy it into addon storage so we use the image taken at ring time rather
        # than capturing a new (potentially delayed) frame from the camera.
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        image_filename = f"doorbell_{timestamp_str}.jpg"
        dest_path = os.path.join(settings.images_path, image_filename)

        if image_path and os.path.isfile(image_path):
            import shutil
            os.makedirs(settings.images_path, exist_ok=True)
            shutil.copy2(image_path, dest_path)
            logger.info("Using pre-captured snapshot", source=image_path, dest=dest_path)
        else:
            captured = await asyncio.to_thread(ha_camera_manager.capture_image, dest_path)
            if not captured:
                logger.error("Failed to capture image from camera")
                raise HTTPException(
                    status_code=500, detail="Failed to capture image from camera"
                )

        image_path = dest_path

        # Run face analysis + weather fetch in parallel
        async def _run_face_analysis() -> Optional[list]:
            if not (settings.face_recognition_enabled and face_recognition_service.is_ready()):
                return None
            try:
                return await asyncio.to_thread(face_recognition_service.analyze_image, image_path)
            except Exception as exc:
                logger.error("Face analysis error", error=str(exc))
                return None

        async def _fetch_weather() -> Optional[dict]:
            if not settings.weather_entity:
                return None
            try:
                ha_api = HomeAssistantAPI()
                return await ha_api.get_weather_data(settings.weather_entity)
            except Exception as exc:
                logger.error("Weather fetch error", error=str(exc))
                return None

        face_raw, weather = await asyncio.gather(_run_face_analysis(), _fetch_weather())

        faces_detected, face_data_json = 0, None
        identified: List[Any] = []
        if face_raw and not isinstance(face_raw, Exception):
            identified = face_recognition_service.identify_faces(face_raw)
            faces_detected = len(identified)
            face_data_json = json.dumps([
                {
                    "name": f.name,
                    "bbox": list(f.bbox),
                    "score": round(f.score, 3),
                    "det_score": round(f.det_score, 3),
                }
                for f in identified
            ])

        # Save event
        event = db.add_doorbell_event(
            image_path=image_path,
            ai_message=ai_message,
            weather_condition=weather.get("condition") if weather else None,
            weather_temperature=weather.get("temperature") if weather else None,
            weather_humidity=weather.get("humidity") if weather else None,
            faces_detected=faces_detected,
            face_data=face_data_json,
        )

        # Save unrecognised face crops (needs event_id, so runs after DB insert)
        for idx, iface in enumerate(identified):
            if iface.name == "Unknown":
                try:
                    crop_path = await asyncio.to_thread(
                        face_recognition_service.save_face_crop,
                        image_path, iface.bbox, event.id, idx
                    )
                    db.add_face_crop(event.id, crop_path)
                except Exception as crop_err:
                    logger.warning("Failed to save face crop", error=str(crop_err))

        # Fire HA event + send notifications in parallel
        await asyncio.gather(
            ha_integration.handle_doorbell_ring(
                {
                    "event_id": event.id,
                    "timestamp": event.timestamp.isoformat(),
                    "image_path": image_path,
                    "ai_message": ai_message,
                }
            ),
            notification_manager.notify_doorbell_ring(
                event_id=event.id,
                image_path=image_path,
                ai_message=ai_message,
            ),
            return_exceptions=True,
        )

        return {
            "success": True,
            "message": "Doorbell ring recorded",
            "event_id": event.id,
            "timestamp": event.timestamp.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error processing doorbell ring", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Doorbell processing failed: {str(e)}"
        )


@app.post("/api/events/{event_id}/comment")
async def update_event_comment(event_id: int, comment: Optional[str] = Form(None)):
    """Add or update a comment on a doorbell event."""
    try:
        event = db.get_doorbell_event(event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        db.update_event_comment(event_id, comment)
        return {"message": "Comment updated", "event_id": event_id, "comment": comment}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating event comment", event_id=event_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/events/delete")
async def delete_events(event_ids: str = Form(...)):
    """Delete multiple events by their IDs."""
    try:
        ids = [int(id.strip()) for id in event_ids.split(",") if id.strip()]

        if not ids:
            raise HTTPException(status_code=400, detail="No event IDs provided")

        deleted_count = db.delete_events(ids)

        return {
            "message": f"Successfully deleted {deleted_count} event(s)",
            "deleted_count": deleted_count,
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid event ID format")
    except Exception as e:
        logger.error("Error deleting events", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ── Images ────────────────────────────────────────────────────────────────────


@app.get("/api/images/{image_name}")
async def get_image(image_name: str):
    """Serve image files."""
    try:
        image_name = sanitize_filename(image_name)
        image_path = os.path.join(settings.images_path, image_name)

        if os.path.isfile(image_path):
            return FileResponse(image_path)

        placeholder_path = create_placeholder_image(image_name)
        if placeholder_path:
            return FileResponse(placeholder_path)

        raise HTTPException(status_code=404, detail="Image not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error serving image", image_name=image_name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ── Settings ──────────────────────────────────────────────────────────────────


@app.get("/api/settings")
async def get_settings():
    """Get current addon configuration settings."""
    return {
        "camera_url": settings.camera_url,
        "camera_entity": settings.camera_entity,
        "storage_path": settings.storage_path,
        "retention_days": settings.retention_days,
        "notification_webhook": settings.notification_webhook,
        "weather_entity": settings.weather_entity,
        "ha_access_token": settings.ha_access_token,
        "app_version": settings.app_version,
    }


@app.post("/api/settings")
async def update_settings(request: Request):
    """Update addon configuration settings."""
    try:
        data = await request.json()

        if "camera_url" in data:
            settings.camera_url = data["camera_url"]
        if "camera_entity" in data:
            settings.camera_entity = data["camera_entity"]
        if "ha_access_token" in data:
            settings.ha_access_token = data["ha_access_token"]
        if "weather_entity" in data:
            settings.weather_entity = data["weather_entity"]
        if "notification_webhook" in data:
            settings.notification_webhook = data["notification_webhook"]
        if "retention_days" in data:
            retention_days = int(data["retention_days"])
            if 1 <= retention_days <= 365:
                settings.retention_days = retention_days
            else:
                raise ValueError("Retention days must be between 1 and 365")
        if "storage_path" in data:
            storage_path = data["storage_path"].strip()
            if storage_path:
                settings.storage_path = storage_path
            else:
                raise ValueError("Storage path cannot be empty")

        settings.save_to_file()

        return {"success": True, "message": "Settings updated successfully"}

    except Exception as e:
        logger.error("Error updating settings", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ── Camera ────────────────────────────────────────────────────────────────────


@app.post("/api/camera/test")
async def test_camera_connection(request: Request):
    """Test camera connection."""
    try:
        data = await request.json()
        source = data.get("source")
        value = data.get("value")

        if source == "url":
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
        cameras = await asyncio.to_thread(ha_camera_manager.get_available_cameras)
        return {"cameras": cameras}
    except Exception as e:
        logger.error("Error getting camera entities", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ── Weather ───────────────────────────────────────────────────────────────────


@app.get("/api/weather-entities")
async def get_available_weather_entities():
    """Get available Home Assistant weather entities."""
    try:
        ha_api = HomeAssistantAPI()
        response = await ha_api._get("/states")
        if not response:
            return {"entities": []}

        weather_entities = [
            {
                "entity_id": state["entity_id"],
                "friendly_name": state.get("attributes", {}).get(
                    "friendly_name", state["entity_id"]
                ),
                "state": state.get("state"),
            }
            for state in response.json()
            if state.get("entity_id", "").startswith("weather.")
        ]
        return {"entities": weather_entities}

    except Exception as e:
        logger.error("Error getting weather entities", error=str(e))
        return {"entities": []}


# ── Notifications ─────────────────────────────────────────────────────────────


@app.post("/api/notifications/test")
async def test_notifications():
    """Test notification system."""
    try:
        await notification_manager.notify_doorbell_ring(
            event_id=0,
            image_path="/test/image.jpg",
            ai_message="Test notification from WhoRang",
        )

        return {
            "success": True,
            "message": "Test notification sent! Check your Home Assistant notifications and webhook.",
        }
    except Exception as e:
        logger.error("Error sending test notification", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to send test notification: {str(e)}"
        )


# ── Storage ───────────────────────────────────────────────────────────────────


@app.post("/api/storage/cleanup")
async def cleanup_storage():
    """Manually trigger cleanup of old data based on retention policy."""
    try:
        events_before = db.get_event_count()
        cleaned_count = db.cleanup_old_events()

        return {
            "success": True,
            "message": f"Cleanup completed! Removed {cleaned_count} old event(s).",
            "events_cleaned": cleaned_count,
            "events_before": events_before,
            "retention_days": settings.retention_days,
        }
    except Exception as e:
        logger.error("Storage cleanup failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@app.get("/api/storage/info")
async def get_storage_info_api():
    """Get current storage usage information."""
    try:
        storage_info = get_storage_usage()

        return {
            "success": True,
            "storage_path": settings.storage_path,
            "total_gb": storage_info.get("total_gb", 0),
            "used_gb": storage_info.get("used_gb", 0),
            "free_gb": storage_info.get("free_gb", 0),
            "usage_percent": storage_info.get("usage_percent", 0),
        }
    except Exception as e:
        logger.error("Failed to get storage info", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to get storage info: {str(e)}"
        )


# ── Face Recognition ─────────────────────────────────────────────────────────


@app.get("/api/face-recognition/status")
async def get_face_recognition_status():
    """Get face recognition service status."""
    persons = db.get_persons()
    return {
        "enabled": settings.face_recognition_enabled,
        "model_loaded": face_recognition_service.is_ready(),
        "model_name": settings.face_recognition_model,
        "person_count": len(persons),
        "threshold": settings.face_recognition_threshold,
    }


@app.get("/api/persons")
async def get_persons():
    """Get all known persons with their sample embeddings."""
    persons = db.get_persons()
    result = []
    for p in persons:
        embeddings = db.get_person_embeddings(p["id"])
        thumb_url = (
            f"api/persons/{p['id']}/thumbnail"
            if p.get("thumbnail_path")
            else None
        )
        samples = [
            {
                "id": e["id"],
                "thumbnail_path": (
                    f"api/persons/{p['id']}/samples/{e['id']}/thumbnail"
                ),
                "created_at": e["created_at"],
            }
            for e in embeddings
        ]
        result.append({
            "id": p["id"],
            "name": p["name"],
            "thumbnail_path": thumb_url,
            "sample_count": len(samples),
            "samples": samples,
        })
    return {"persons": result}


@app.post("/api/persons", status_code=201)
async def add_person(name: str = Form(...), image: UploadFile = File(...)):
    """Add a known person from an uploaded image."""
    if not settings.face_recognition_enabled:
        raise HTTPException(
            status_code=503, detail="Face recognition is not enabled"
        )
    name = name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name must not be empty")
    import tempfile
    suffix = os.path.splitext(image.filename or ".jpg")[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await image.read())
        tmp_path = tmp.name
    try:
        person = await asyncio.to_thread(
            face_recognition_service.add_person, name, tmp_path
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Error adding person", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
    # Return full person shape
    embeddings = db.get_person_embeddings(person["id"])
    samples = [
        {
            "id": e["id"],
            "thumbnail_path": (
                f"api/persons/{person['id']}/samples/{e['id']}/thumbnail"
            ),
            "created_at": e["created_at"],
        }
        for e in embeddings
    ]
    return {
        "id": person["id"],
        "name": person["name"],
        "thumbnail_path": (
            f"api/persons/{person['id']}/thumbnail"
            if person.get("thumbnail_path")
            else None
        ),
        "sample_count": len(samples),
        "samples": samples,
    }


@app.patch("/api/persons/{person_id}")
async def rename_person(person_id: int, request: Request):
    """Rename a known person."""
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name must not be empty")
    if not db.rename_person(person_id, name):
        raise HTTPException(status_code=404, detail="Person not found")
    face_recognition_service.refresh_embeddings_cache()
    return {"id": person_id, "name": name}


@app.delete("/api/persons/{person_id}", status_code=204)
async def delete_person(person_id: int):
    """Delete a known person and all their sample thumbnails."""
    deleted = await asyncio.to_thread(
        face_recognition_service.delete_person, person_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Person not found")


@app.get("/api/persons/{person_id}/thumbnail")
async def get_person_thumbnail(person_id: int):
    """Serve person avatar thumbnail -- reads path from DB."""
    person = db.get_person(person_id)
    if not person or not person.get("thumbnail_path"):
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    if not os.path.isfile(person["thumbnail_path"]):
        raise HTTPException(status_code=404, detail="Thumbnail file missing")
    return FileResponse(person["thumbnail_path"])


@app.get("/api/persons/{person_id}/samples/{emb_id}/thumbnail")
async def get_sample_thumbnail(person_id: int, emb_id: int):
    """Serve a specific sample thumbnail."""
    rows = db.get_person_embeddings(person_id)
    emb = next((e for e in rows if e["id"] == emb_id), None)
    if not emb or not emb.get("thumbnail_path"):
        raise HTTPException(
            status_code=404, detail="Sample thumbnail not found"
        )
    if not os.path.isfile(emb["thumbnail_path"]):
        raise HTTPException(status_code=404, detail="Thumbnail file missing")
    return FileResponse(emb["thumbnail_path"])


@app.post("/api/persons/{person_id}/samples", status_code=201)
async def add_person_sample(
    person_id: int, image: UploadFile = File(...)
):
    """Add another face sample to an existing person."""
    if not settings.face_recognition_enabled:
        raise HTTPException(
            status_code=503, detail="Face recognition is not enabled"
        )
    person = db.get_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    import tempfile
    import io as _io
    import numpy as np
    from PIL import Image, ImageOps
    suffix = os.path.splitext(image.filename or ".jpg")[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await image.read())
        tmp_path = tmp.name
    try:
        faces = await asyncio.to_thread(
            face_recognition_service.analyze_image, tmp_path
        )
        if not faces:
            raise HTTPException(
                status_code=422, detail="No face detected in uploaded image"
            )
        best_face = max(faces, key=lambda f: f.det_score)
        buf = _io.BytesIO()
        np.save(buf, best_face.embedding)
        emb_bytes = buf.getvalue()
        # Crop thumbnail
        os.makedirs(settings.persons_path, exist_ok=True)
        img_pil = ImageOps.exif_transpose(
            Image.open(tmp_path)
        ).convert("RGB")
        x, y, w, h = best_face.bbox
        padding = int(max(w, h) * 0.2)
        crop = img_pil.crop((
            max(0, x - padding),
            max(0, y - padding),
            min(img_pil.width, x + w + padding),
            min(img_pil.height, y + h + padding),
        )).resize((200, 200))
        tmp_thumb = os.path.join(
            settings.persons_path, f"{person_id}_tmp.jpg"
        )
        crop.save(tmp_thumb, "JPEG")
        emb_id = db.add_person_embedding(person_id, emb_bytes, None)
        final_thumb = os.path.join(
            settings.persons_path, f"{person_id}_{emb_id}.jpg"
        )
        os.rename(tmp_thumb, final_thumb)
        db.update_person_embedding_thumbnail(emb_id, final_thumb)
        # Set avatar if currently NULL
        if not person.get("thumbnail_path"):
            db.update_person_thumbnail(person_id, final_thumb)
        face_recognition_service.refresh_embeddings_cache()
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
    emb_rows = db.get_person_embeddings(person_id)
    emb_row = next((e for e in emb_rows if e["id"] == emb_id), None)
    return {
        "id": emb_id,
        "person_id": person_id,
        "thumbnail_path": (
            f"api/persons/{person_id}/samples/{emb_id}/thumbnail"
        ),
        "created_at": emb_row["created_at"] if emb_row else None,
    }


@app.delete("/api/persons/{person_id}/samples/{emb_id}", status_code=204)
async def delete_person_sample(person_id: int, emb_id: int):
    """Remove a face sample from a person."""
    rows = db.get_person_embeddings(person_id)
    emb = next((e for e in rows if e["id"] == emb_id), None)
    if not emb:
        raise HTTPException(status_code=404, detail="Sample not found")
    # Delete thumbnail file
    if emb.get("thumbnail_path"):
        try:
            os.remove(emb["thumbnail_path"])
        except Exception:
            pass
    db.delete_person_embedding(emb_id)
    # Update avatar if this was the avatar
    person = db.get_person(person_id)
    if person and person.get("thumbnail_path") == emb.get("thumbnail_path"):
        remaining = db.get_person_embeddings(person_id)
        new_thumb = remaining[0]["thumbnail_path"] if remaining else None
        db.update_person_thumbnail(person_id, new_thumb)
    face_recognition_service.refresh_embeddings_cache()


# ── Face Crops Inbox ──────────────────────────────────────────────────────────


@app.get("/api/face-crops")
async def get_face_crops(dismissed: bool = False, count_only: bool = False):
    """Get unrecognised face crops inbox."""
    if not settings.face_recognition_enabled:
        return {"count": 0} if count_only else {"crops": []}
    if count_only:
        return {"count": db.get_face_crop_count(dismissed=dismissed)}
    crops = db.get_face_crops(dismissed=dismissed)
    result = []
    for c in crops:
        result.append({
            "id": c["id"],
            "event_id": c["event_id"],
            "image_path": f"api/face-crops/{c['id']}/image",
            "dismissed": bool(c["dismissed"]),
            "created_at": c["created_at"],
            "event_timestamp": c["event_timestamp"],
        })
    return {"crops": result}


@app.get("/api/face-crops/{crop_id}/image")
async def get_face_crop_image(crop_id: int):
    """Serve a face crop image."""
    crop = db.get_face_crop(crop_id)
    if not crop:
        raise HTTPException(status_code=404, detail="Crop not found")
    if not os.path.isfile(crop["image_path"]):
        raise HTTPException(status_code=404, detail="Crop file missing")
    return FileResponse(crop["image_path"])


@app.post("/api/face-crops/{crop_id}/dismiss", status_code=204)
async def dismiss_face_crop(crop_id: int):
    """Dismiss a face crop without assigning."""
    crop = db.get_face_crop(crop_id)
    if not crop:
        raise HTTPException(status_code=404, detail="Crop not found")
    db.dismiss_face_crop(crop_id)


@app.post("/api/face-crops/{crop_id}/assign")
async def assign_face_crop(crop_id: int, request: Request):
    """Assign a face crop to an existing person or create a new one."""
    if not settings.face_recognition_enabled:
        raise HTTPException(status_code=503, detail="Face recognition is not enabled")
    data = await request.json()
    has_person_id = "person_id" in data
    has_name = bool("name" in data and data["name"])
    if has_person_id == has_name:  # both or neither
        raise HTTPException(
            status_code=422,
            detail="Provide exactly one of person_id or name",
        )
    crop = db.get_face_crop(crop_id)
    if not crop:
        raise HTTPException(status_code=404, detail="Crop not found")

    created_person_id = None
    if has_name:
        created_person_id = db.add_person(data["name"].strip())
        person_id = created_person_id
    else:
        person_id = int(data["person_id"])

    try:
        faces = await asyncio.to_thread(
            face_recognition_service.analyze_image, crop["image_path"]
        )
        if not faces:
            if created_person_id:
                db.delete_person(created_person_id)
            raise HTTPException(status_code=422, detail="No face detected in crop image")

        best_face = max(faces, key=lambda f: f.det_score)
        import io as _io
        import numpy as np
        buf = _io.BytesIO()
        np.save(buf, best_face.embedding)
        emb_bytes = buf.getvalue()

        os.makedirs(settings.persons_path, exist_ok=True)
        from PIL import Image, ImageOps
        img_pil = ImageOps.exif_transpose(
            Image.open(crop["image_path"])
        ).convert("RGB")
        x, y, w, h = best_face.bbox
        padding = int(max(w, h) * 0.2)
        thumb = img_pil.crop((
            max(0, x - padding), max(0, y - padding),
            min(img_pil.width, x + w + padding), min(img_pil.height, y + h + padding),
        )).resize((200, 200))
        tmp_thumb = os.path.join(settings.persons_path, f"{person_id}_tmp.jpg")
        thumb.save(tmp_thumb, "JPEG")
        emb_id = db.add_person_embedding(person_id, emb_bytes, None)
        final_thumb = os.path.join(settings.persons_path, f"{person_id}_{emb_id}.jpg")
        os.rename(tmp_thumb, final_thumb)
        db.update_person_embedding_thumbnail(emb_id, final_thumb)
        person = db.get_person(person_id)
        if person and not person.get("thumbnail_path"):
            db.update_person_thumbnail(person_id, final_thumb)
        db.dismiss_face_crop(crop_id)
        face_recognition_service.refresh_embeddings_cache()

        name = data.get("name") or (person["name"] if person else "Unknown")
        return {"person_id": person_id, "embedding_id": emb_id, "name": name}

    except HTTPException:
        raise
    except Exception as e:
        if created_person_id:
            try:
                db.delete_person(created_person_id)
            except Exception:
                pass
        logger.error("Error assigning face crop", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/events/{event_id}/faces")
async def get_event_faces(event_id: int):
    """Get face data for a specific event."""
    event = db.get_doorbell_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    faces = json.loads(event.face_data) if event.face_data else []
    return {
        "event_id": event_id,
        "faces_detected": event.faces_detected or 0,
        "faces": faces,
    }


@app.post("/api/settings/face-recognition")
async def update_face_recognition_settings(request: Request):
    """Update face recognition settings."""
    try:
        data = await request.json()
        was_disabled = not settings.face_recognition_enabled

        if "enabled" in data:
            settings.face_recognition_enabled = bool(data["enabled"])
        if "model" in data and data["model"] in ("buffalo_sc", "buffalo_s", "buffalo_l"):
            settings.face_recognition_model = data["model"]
        if "threshold" in data:
            threshold = float(data["threshold"])
            if 0.1 <= threshold <= 0.99:
                settings.face_recognition_threshold = threshold

        settings.save_to_file()

        # Kick off model loading if just enabled
        if settings.face_recognition_enabled and (was_disabled or not face_recognition_service.is_ready()):
            asyncio.create_task(face_recognition_service.initialize())

        return {"success": True, "message": "Face recognition settings updated"}
    except Exception as e:
        logger.error("Error updating face recognition settings", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8099, log_level="info")
