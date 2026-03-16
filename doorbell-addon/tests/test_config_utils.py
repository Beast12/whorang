"""Tests for config.py and utils.py additions."""
import os
import pytest
from unittest.mock import patch
import src.config as config_mod
import src.utils as utils_mod


def test_face_crops_path_property(tmp_path):
    """face_crops_path should be {storage_path}/face_crops."""
    with patch.object(config_mod.settings, 'storage_path', str(tmp_path)):
        assert config_mod.settings.face_crops_path == str(tmp_path / "face_crops")


def test_ensure_directories_creates_face_crops_path(tmp_path):
    """ensure_directories must create the face_crops directory."""
    with patch.object(config_mod.settings, 'storage_path', str(tmp_path)):
        with patch('src.utils.settings', config_mod.settings):
            utils_mod.ensure_directories()
    assert (tmp_path / "face_crops").is_dir()
