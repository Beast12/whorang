"""Ring event pipeline — owns the complete doorbell ring flow."""

import asyncio
import json
import os
import shutil
from datetime import datetime
from typing import Optional

import structlog

from .config import settings
from .database import db
from .face_recognition_service import face_recognition_service
from .ha_camera import ha_camera_manager
from .ha_integration import ha_integration
from .utils import HomeAssistantAPI
from .utils import notification_manager

logger = structlog.get_logger()


async def run_ring_pipeline(
    image_path: Optional[str] = None,
    ai_message: Optional[str] = None,
) -> dict:
    """Run the complete doorbell ring pipeline.

    Args:
        image_path: Path to a pre-captured snapshot. If provided and the file
                    exists, it is used instead of capturing from the camera.
        ai_message: Caller-provided description. If set, the LLM call is skipped.

    Returns:
        {"event_id": int, "ai_message": str, "ai_title": str}

    Raises:
        RuntimeError: Only if image capture fails (non-degradable).
    """
    # ── Step 1: Capture image ──────────────────────────────────────────────
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    image_filename = f"doorbell_{timestamp_str}.jpg"
    dest_path = os.path.join(settings.images_path, image_filename)

    if image_path and os.path.isfile(image_path):
        os.makedirs(settings.images_path, exist_ok=True)
        shutil.copy2(image_path, dest_path)
        logger.info("Using pre-captured snapshot", source=image_path, dest=dest_path)
    else:
        captured = await asyncio.to_thread(ha_camera_manager.capture_image, dest_path)
        if not captured:
            raise RuntimeError("Failed to capture image from camera")

    image_path = dest_path

    # ── Step 2: Write public copy (must complete before LLM call) ──────────
    public_filename: Optional[str] = None
    if settings.public_image_path:
        try:
            os.makedirs(settings.public_image_path, exist_ok=True)
            public_filename = image_filename
            shutil.copy2(image_path, os.path.join(settings.public_image_path, public_filename))
        except Exception as e:
            logger.warning("Failed to write public image copy", error=str(e))
            public_filename = None

    # ── Step 3: Parallel analysis ──────────────────────────────────────────
    async def _llm_call() -> tuple:
        if ai_message is not None:
            logger.debug("LLM skipped — ai_message provided by caller")
            return ai_message, "Doorbell"
        if not settings.llmvision_enabled:
            logger.debug("LLM skipped — llmvision_enabled=false")
            return settings.default_message, "Doorbell"
        if not settings.llmvision_provider:
            logger.debug("LLM skipped — no provider configured")
            return settings.default_message, "Doorbell"
        if not settings.public_image_path:
            logger.debug("LLM skipped — no public_image_path configured")
            return settings.default_message, "Doorbell"
        if not public_filename:
            logger.debug("LLM skipped — public image write failed")
            return settings.default_message, "Doorbell"
        ha_api = HomeAssistantAPI()
        try:
            return await ha_api.call_llmvision(
                image_file=os.path.join(settings.public_image_path, public_filename),
                provider=settings.llmvision_provider,
                prompt=settings.llmvision_prompt,
                max_tokens=settings.llmvision_max_tokens,
            )
        except Exception as e:
            logger.warning("LLM call failed, using default message", error=str(e))
            return settings.default_message, "Doorbell"

    async def _face_analysis() -> Optional[list]:
        if not (settings.face_recognition_enabled and face_recognition_service.is_ready()):
            return None
        try:
            return await asyncio.to_thread(face_recognition_service.analyze_image, image_path)
        except Exception as e:
            logger.error("Face analysis error", error=str(e))
            return None

    async def _weather_fetch() -> Optional[dict]:
        if not settings.weather_entity:
            return None
        try:
            ha_api = HomeAssistantAPI()
            return await ha_api.get_weather_data(settings.weather_entity)
        except Exception as e:
            logger.error("Weather fetch error", error=str(e))
            return None

    results = await asyncio.gather(
        _llm_call(), _face_analysis(), _weather_fetch(),
        return_exceptions=True,
    )
    llm_result, face_raw, weather = results

    if isinstance(llm_result, Exception) or not isinstance(llm_result, tuple):
        resolved_message, resolved_title = settings.default_message, "Doorbell"
    else:
        resolved_message, resolved_title = llm_result

    if isinstance(face_raw, Exception):
        face_raw = None
    if isinstance(weather, Exception):
        weather = None

    # Process face results
    identified, faces_detected, face_data_json = [], 0, None
    if face_raw:
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

    # ── Step 4: Save event ─────────────────────────────────────────────────
    event = db.add_doorbell_event(
        image_path=image_path,
        ai_message=resolved_message,
        weather_condition=weather.get("condition") if weather else None,
        weather_temperature=weather.get("temperature") if weather else None,
        weather_humidity=weather.get("humidity") if weather else None,
        faces_detected=faces_detected,
        face_data=face_data_json,
    )

    # ── Step 5: Save face crops ────────────────────────────────────────────
    for idx, iface in enumerate(identified):
        if iface.name == "Unknown":
            try:
                crop_path = await asyncio.to_thread(
                    face_recognition_service.save_face_crop,
                    image_path, iface.bbox, event.id, idx,
                )
                db.add_face_crop(event.id, crop_path)
            except Exception as crop_err:
                logger.warning("Failed to save face crop", error=str(crop_err))

    # ── Step 6: Send notifications ─────────────────────────────────────────
    notify_tasks = []
    if settings.ha_notify_services:
        ha_api = HomeAssistantAPI()
        for svc in settings.ha_notify_services:
            notify_tasks.append(
                ha_api.send_ha_notification(
                    service_name=svc,
                    message=resolved_message,
                    title=resolved_title,
                    image_filename=public_filename,
                )
            )
    if settings.notification_webhook:
        notify_tasks.append(
            notification_manager._send_webhook_notification({
                "title": resolved_title,
                "message": resolved_message,
                "event": "doorbell_ring",
                "event_id": event.id,
                "image_path": image_path,
                "ai_message": resolved_message,
                "timestamp": event.timestamp.isoformat(),
            })
        )
    if notify_tasks:
        await asyncio.gather(*notify_tasks, return_exceptions=True)

    # ── Step 7: Fire HA event + update sensors ─────────────────────────────
    try:
        await ha_integration.handle_doorbell_ring({
            "event_id": event.id,
            "timestamp": event.timestamp.isoformat(),
            "image_path": image_path,
            "ai_message": resolved_message,
        })
    except Exception as e:
        logger.error("HA integration error", error=str(e))

    return {
        "event_id": event.id,
        "ai_message": resolved_message,
        "ai_title": resolved_title,
    }
