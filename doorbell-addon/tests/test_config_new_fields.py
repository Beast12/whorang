"""Tests for new automation-integration settings fields."""
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def make_settings(tmp_path):
    from src.config import Settings
    s = Settings()
    s.storage_path = str(tmp_path)
    return s


def test_new_fields_have_correct_defaults(tmp_path):
    s = make_settings(tmp_path)
    assert s.llmvision_enabled is False
    assert s.llmvision_provider is None
    assert s.llmvision_model == "gpt-4o-mini"
    assert "security guard" in s.llmvision_prompt
    assert s.llmvision_max_tokens == 100
    assert s.default_message == "Someone is at the door"
    assert s.ha_notify_services == []
    assert s.public_image_path is None
    assert s.trigger_entity is None


def test_new_fields_persist_and_reload(tmp_path):
    s = make_settings(tmp_path)
    s.llmvision_enabled = True
    s.llmvision_provider = "my_provider"
    s.llmvision_model = "gpt-4o"
    s.llmvision_max_tokens = 150
    s.default_message = "Hi there"
    s.ha_notify_services = ["notify.mobile_app_phone"]
    s.public_image_path = "/config/www"
    s.trigger_entity = "binary_sensor.doorbell"
    s.save_to_file()

    s2 = make_settings(tmp_path)
    s2.load_from_file()
    assert s2.llmvision_enabled is True
    assert s2.llmvision_provider == "my_provider"
    assert s2.llmvision_model == "gpt-4o"
    assert s2.llmvision_max_tokens == 150
    assert s2.default_message == "Hi there"
    assert s2.ha_notify_services == ["notify.mobile_app_phone"]
    assert s2.public_image_path == "/config/www"
    assert s2.trigger_entity == "binary_sensor.doorbell"
