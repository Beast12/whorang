"""Main FastAPI application for the WhoRang doorbell addon."""

import asyncio
import os
from datetime import datetime
from typing import Optional

import requests
import structlog
import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .database import db
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


@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    logger.info("Starting WhoRang doorbell addon", version=settings.app_version)
    ensure_directories()
    await ha_integration.initialize()
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
):
    """Handle a doorbell ring event — capture image and record the event."""
    logger.info("Doorbell ring event received", ai_message=ai_message)
    try:
        # Capture image (blocking — runs in thread pool)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        image_filename = f"doorbell_{timestamp_str}.jpg"
        image_path = os.path.join(settings.images_path, image_filename)

        captured = await asyncio.to_thread(ha_camera_manager.capture_image, image_path)
        if not captured:
            logger.error("Failed to capture image from camera")
            raise HTTPException(
                status_code=500, detail="Failed to capture image from camera"
            )

        # Fetch weather in parallel with nothing else yet (cheap; needed before DB write)
        weather = None
        if settings.weather_entity:
            ha_api = HomeAssistantAPI()
            weather = await ha_api.get_weather_data(settings.weather_entity)

        # Save event
        event = db.add_doorbell_event(
            image_path=image_path,
            ai_message=ai_message,
            weather_condition=weather.get("condition") if weather else None,
            weather_temperature=weather.get("temperature") if weather else None,
            weather_humidity=weather.get("humidity") if weather else None,
        )

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


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8099, log_level="info")
