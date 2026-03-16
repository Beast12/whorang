"""Optional face recognition service using InsightFace."""

import io
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import structlog

from .config import settings
from .database import db

logger = structlog.get_logger()


@dataclass
class FaceResult:
    """Raw face detection result."""

    bbox: tuple  # (x, y, w, h)
    embedding: Any  # np.ndarray
    det_score: float


@dataclass
class IdentifiedFace:
    """Face matched against known persons."""

    bbox: tuple
    name: str        # person name or "Unknown"
    score: float     # cosine similarity (0.0 for Unknown)
    det_score: float
    person_id: Optional[int] = None  # None for Unknown


class FaceRecognitionService:
    """Singleton service for face detection and recognition."""

    def __init__(self):
        self._model = None
        self._ready = False
        self._embeddings_cache: Dict[int, Any] = {}  # {embedding_id: (person_id, name, emb)}

    def is_ready(self) -> bool:
        return self._ready

    async def initialize(self) -> None:
        """Load the InsightFace model in a thread pool (non-blocking startup)."""
        import asyncio
        try:
            await asyncio.to_thread(self._load_model)
            self._refresh_embeddings_cache_sync()
            self._ready = True
            logger.info("Face recognition model loaded", model=settings.face_recognition_model)
        except Exception as e:
            logger.error("Failed to load face recognition model", error=str(e))

    def _load_model(self) -> None:
        """Load InsightFace model (runs in thread pool)."""
        os.environ["INSIGHTFACE_HOME"] = settings.insightface_models_path
        from insightface.app import FaceAnalysis  # type: ignore
        model = FaceAnalysis(
            name=settings.face_recognition_model,
            allowed_modules=["detection", "recognition"],
        )
        model.prepare(ctx_id=-1, det_size=(640, 640))
        self._model = model

    def analyze_image(self, image_path: str) -> List[FaceResult]:
        """Detect faces in an image file. Synchronous — call via asyncio.to_thread."""
        if not self._ready or self._model is None:
            return []
        try:
            import numpy as np
            from PIL import Image, ImageOps
            img = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
            img_array = np.array(img)
            faces = self._model.get(img_array)
            results = []
            for face in faces:
                x1, y1, x2, y2 = face.bbox.astype(int)
                bbox = (int(x1), int(y1), int(x2 - x1), int(y2 - y1))
                results.append(FaceResult(
                    bbox=bbox,
                    embedding=face.embedding,
                    det_score=float(face.det_score),
                ))
            return results
        except Exception as e:
            logger.error("Face analysis failed", image_path=image_path, error=str(e))
            return []

    def identify_faces(self, faces: List[FaceResult]) -> List[IdentifiedFace]:
        """Match detected faces against known persons using cosine similarity."""
        import numpy as np
        identified = []
        for face in faces:
            best_name = "Unknown"
            best_score = 0.0
            emb = face.embedding
            norm_emb = emb / (np.linalg.norm(emb) + 1e-10)
            for person_id, known_emb in self._embeddings_cache.items():
                norm_known = known_emb / (np.linalg.norm(known_emb) + 1e-10)
                score = float(np.dot(norm_emb, norm_known))
                if score > best_score and score >= settings.face_recognition_threshold:
                    best_score = score
                    person = self._get_person_name(person_id)
                    best_name = person if person else "Unknown"
            identified.append(IdentifiedFace(
                bbox=face.bbox,
                name=best_name,
                score=round(best_score, 3),
                det_score=round(face.det_score, 3),
            ))
        return identified

    def _get_person_name(self, person_id: int) -> Optional[str]:
        from .database import db
        person = db.get_person(person_id)
        return person["name"] if person else None

    def add_person(self, name: str, image_path: str) -> dict:
        """Detect face in image, store embedding + thumbnail. Returns person dict."""
        import io
        import numpy as np
        from PIL import Image, ImageOps
        from .database import db

        os.makedirs(settings.persons_path, exist_ok=True)

        faces = self.analyze_image(image_path)
        if not faces:
            raise ValueError("No face detected in the uploaded image")

        # Pick face with highest detection confidence
        best_face = max(faces, key=lambda f: f.det_score)

        # Serialize embedding
        buf = io.BytesIO()
        np.save(buf, best_face.embedding)
        embedding_bytes = buf.getvalue()

        # Save to DB first to get ID
        person_id = db.add_person(name, embedding_bytes, None)

        # Crop and save thumbnail
        try:
            img = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
            x, y, w, h = best_face.bbox
            padding = int(max(w, h) * 0.2)
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(img.width, x + w + padding)
            y2 = min(img.height, y + h + padding)
            thumb = img.crop((x1, y1, x2, y2)).resize((200, 200))
            thumb_path = os.path.join(settings.persons_path, f"{person_id}.jpg")
            thumb.save(thumb_path, "JPEG")
            db.update_person_thumbnail(person_id, thumb_path)
        except Exception as e:
            logger.warning("Failed to save person thumbnail", error=str(e))
            thumb_path = None

        # Update in-memory cache
        self._embeddings_cache[person_id] = best_face.embedding

        return {"id": person_id, "name": name, "thumbnail_path": thumb_path}

    def delete_person(self, person_id: int) -> bool:
        """Remove person from DB and cache."""
        from .database import db
        deleted = db.delete_person(person_id)
        if deleted:
            self._embeddings_cache.pop(person_id, None)
            thumb = os.path.join(settings.persons_path, f"{person_id}.jpg")
            try:
                if os.path.exists(thumb):
                    os.remove(thumb)
            except Exception:
                pass
        return deleted

    def refresh_embeddings_cache(self) -> None:
        """Reload all embeddings from DB into memory."""
        self._refresh_embeddings_cache_sync()

    def _refresh_embeddings_cache_sync(self) -> None:
        import io
        import numpy as np
        cache: Dict[int, Any] = {}
        for row in db.get_all_embeddings():
            try:
                buf = io.BytesIO(row["embedding"])
                emb = np.load(buf, allow_pickle=False)
                cache[row["id"]] = (row["person_id"], row["name"], emb)
            except Exception as e:
                logger.warning(
                    "Failed to load embedding",
                    embedding_id=row["id"],
                    error=str(e),
                )
        self._embeddings_cache = cache
        logger.info("Embeddings cache refreshed", count=len(cache))


# Module-level singleton
face_recognition_service = FaceRecognitionService()
