"""Tests for face_recognition_service.py."""
import io
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# conftest.py inserts doorbell-addon/ so 'src' package is importable


def make_embedding_bytes(values):
    import numpy as np
    buf = io.BytesIO()
    np.save(buf, np.array(values, dtype="float32"))
    return buf.getvalue()


def test_identified_face_has_person_id_field():
    """IdentifiedFace must have a person_id field."""
    from src.face_recognition_service import IdentifiedFace
    face = IdentifiedFace(bbox=(0, 0, 10, 10), name="Alice", score=0.9, det_score=0.99)
    assert hasattr(face, 'person_id')
    assert face.person_id is None  # default


def test_refresh_cache_builds_new_format(tmp_path):
    """_refresh_embeddings_cache_sync must build {emb_id: (pid, name, emb)} cache."""
    import numpy as np
    from src.face_recognition_service import FaceRecognitionService

    emb_bytes = make_embedding_bytes([0.1, 0.2, 0.3])
    mock_db = MagicMock()
    mock_db.get_all_embeddings.return_value = [
        {"id": 5, "person_id": 1, "name": "Alice", "embedding": emb_bytes}
    ]

    svc = FaceRecognitionService.__new__(FaceRecognitionService)
    svc._embeddings_cache = {}
    svc._ready = False
    svc._model = None

    with patch('src.face_recognition_service.db', mock_db):
        svc._refresh_embeddings_cache_sync()

    assert 5 in svc._embeddings_cache
    person_id, person_name, emb = svc._embeddings_cache[5]
    assert person_id == 1
    assert person_name == "Alice"
    assert isinstance(emb, np.ndarray)


def make_service_with_cache(embeddings):
    """Build a FaceRecognitionService with a pre-populated cache."""
    import numpy as np
    from src.face_recognition_service import FaceRecognitionService
    svc = FaceRecognitionService.__new__(FaceRecognitionService)
    svc._model = None
    svc._ready = True
    svc._embeddings_cache = {}
    for emb_id, person_id, name, vec in embeddings:
        svc._embeddings_cache[emb_id] = (person_id, name, np.array(vec, dtype="float32"))
    return svc


def test_identify_faces_matches_known_person():
    """identify_faces returns person name when cosine similarity exceeds threshold."""
    import numpy as np
    from src.face_recognition_service import FaceResult
    # Alice's embedding is [1, 0, 0]
    svc = make_service_with_cache([(1, 10, "Alice", [1.0, 0.0, 0.0])])
    mock_settings = MagicMock()
    mock_settings.face_recognition_threshold = 0.45
    face = FaceResult(bbox=(0, 0, 50, 50), embedding=np.array([1.0, 0.0, 0.0]), det_score=0.99)
    with patch('src.face_recognition_service.settings', mock_settings):
        results = svc.identify_faces([face])
    assert results[0].name == "Alice"
    assert results[0].person_id == 10


def test_identify_faces_unknown_below_threshold():
    import numpy as np
    from src.face_recognition_service import FaceResult
    svc = make_service_with_cache([(1, 10, "Alice", [1.0, 0.0, 0.0])])
    mock_settings = MagicMock()
    mock_settings.face_recognition_threshold = 0.45
    # Orthogonal vector — similarity = 0
    face = FaceResult(bbox=(0, 0, 50, 50), embedding=np.array([0.0, 1.0, 0.0]), det_score=0.99)
    with patch('src.face_recognition_service.settings', mock_settings):
        results = svc.identify_faces([face])
    assert results[0].name == "Unknown"
    assert results[0].person_id is None


def test_identify_faces_picks_best_across_multiple_embeddings():
    """Multiple embeddings for the same person: pick best score."""
    import numpy as np
    from src.face_recognition_service import FaceResult
    # Alice has two embeddings; Bob has one
    svc = make_service_with_cache([
        (1, 10, "Alice", [0.9, 0.1, 0.0]),
        (2, 10, "Alice", [1.0, 0.0, 0.0]),  # better match for [1,0,0]
        (3, 20, "Bob",   [0.0, 1.0, 0.0]),
    ])
    mock_settings = MagicMock()
    mock_settings.face_recognition_threshold = 0.45
    face = FaceResult(bbox=(0, 0, 50, 50), embedding=np.array([1.0, 0.0, 0.0]), det_score=0.99)
    with patch('src.face_recognition_service.settings', mock_settings):
        results = svc.identify_faces([face])
    assert results[0].name == "Alice"
    assert results[0].person_id == 10


def test_identify_faces_picks_best_person_not_best_embedding():
    """When two persons both exceed threshold, pick the one with higher score."""
    import numpy as np
    from src.face_recognition_service import FaceResult
    svc = make_service_with_cache([
        (1, 10, "Alice", [0.95, 0.05, 0.0]),
        (2, 20, "Bob",   [0.80, 0.20, 0.0]),
    ])
    mock_settings = MagicMock()
    mock_settings.face_recognition_threshold = 0.45
    face = FaceResult(bbox=(0, 0, 50, 50), embedding=np.array([1.0, 0.0, 0.0]), det_score=0.99)
    with patch('src.face_recognition_service.settings', mock_settings):
        results = svc.identify_faces([face])
    assert results[0].name == "Alice"


def test_save_face_crop_creates_file(tmp_path):
    """save_face_crop must write a JPEG to face_crops_path."""
    from PIL import Image
    from src.face_recognition_service import FaceRecognitionService

    # Create a dummy image
    img = Image.new("RGB", (200, 200), color=(128, 64, 32))
    img_path = str(tmp_path / "test_img.jpg")
    img.save(img_path, "JPEG")

    svc = FaceRecognitionService.__new__(FaceRecognitionService)
    mock_settings = MagicMock()
    mock_settings.face_crops_path = str(tmp_path / "crops")

    with patch('src.face_recognition_service.settings', mock_settings):
        path = svc.save_face_crop(img_path, (10, 10, 80, 80), event_id=42, face_idx=0)

    assert os.path.isfile(path)
    assert "42_0.jpg" in path
    saved = Image.open(path)
    assert saved.size == (200, 200)


def test_save_face_crop_uses_event_idx_naming(tmp_path):
    """File name must be {event_id}_{face_idx}.jpg."""
    from PIL import Image
    from src.face_recognition_service import FaceRecognitionService
    img = Image.new("RGB", (300, 300))
    img_path = str(tmp_path / "img.jpg")
    img.save(img_path, "JPEG")
    svc = FaceRecognitionService.__new__(FaceRecognitionService)
    mock_settings = MagicMock()
    mock_settings.face_crops_path = str(tmp_path / "crops")
    with patch('src.face_recognition_service.settings', mock_settings):
        path = svc.save_face_crop(img_path, (0, 0, 100, 100), event_id=7, face_idx=2)
    assert path.endswith("7_2.jpg")
