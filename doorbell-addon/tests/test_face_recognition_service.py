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
