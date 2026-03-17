"""Tests for classify_notify_service() and HomeAssistantAPI.send_ha_notification()."""
import os
import sys
import pytest
from unittest.mock import AsyncMock, patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils import classify_notify_service, HomeAssistantAPI


# ── classify_notify_service ────────────────────────────────────────────────

def test_mobile_app_is_image_capable():
    assert classify_notify_service("mobile_app_my_phone") == "image"


def test_telegram_is_image_capable():
    assert classify_notify_service("telegram_bot") == "image"


def test_html5_is_image_capable():
    assert classify_notify_service("html5_browser") == "image"


def test_tts_is_audio_only():
    assert classify_notify_service("tts_google_say") == "audio"


def test_alexa_media_is_audio_only():
    assert classify_notify_service("alexa_media_kitchen") == "audio"


def test_google_is_audio_only():
    assert classify_notify_service("google_assistant") == "audio"


def test_unknown_service_is_full():
    assert classify_notify_service("pushover") == "full"
    assert classify_notify_service("smtp_email") == "full"


# ── send_ha_notification ───────────────────────────────────────────────────

@pytest.fixture
def ha_api():
    return HomeAssistantAPI()


@pytest.mark.asyncio
async def test_image_capable_includes_data_image(ha_api):
    mock_post = AsyncMock(return_value=None)
    with patch.object(ha_api, '_post', new=mock_post):
        await ha_api.send_ha_notification(
            service_name="notify.mobile_app_phone",
            message="Someone at door",
            title="Doorbell",
            image_filename="doorbell_123.jpg",
        )
    path, payload = mock_post.call_args[0]
    assert path == "/services/notify/mobile_app_phone"
    assert payload["title"] == "Doorbell"
    assert payload["message"] == "Someone at door"
    assert payload["data"]["image"] == "/local/doorbell_123.jpg"
    assert payload["data"]["priority"] == "high"


@pytest.mark.asyncio
async def test_image_capable_no_filename_omits_data_image(ha_api):
    mock_post = AsyncMock(return_value=None)
    with patch.object(ha_api, '_post', new=mock_post):
        await ha_api.send_ha_notification(
            service_name="notify.mobile_app_phone",
            message="Someone at door",
            title="Doorbell",
            image_filename=None,
        )
    _, payload = mock_post.call_args[0]
    assert "data" not in payload


@pytest.mark.asyncio
async def test_audio_only_sends_message_only(ha_api):
    mock_post = AsyncMock(return_value=None)
    with patch.object(ha_api, '_post', new=mock_post):
        await ha_api.send_ha_notification(
            service_name="notify.tts_kitchen",
            message="Someone at door",
            title="Doorbell",
            image_filename="doorbell_123.jpg",
        )
    path, payload = mock_post.call_args[0]
    assert path == "/services/notify/tts_kitchen"
    assert "title" not in payload
    assert payload["message"] == "Someone at door"


@pytest.mark.asyncio
async def test_notify_prefix_stripped_from_path(ha_api):
    mock_post = AsyncMock(return_value=None)
    with patch.object(ha_api, '_post', new=mock_post):
        await ha_api.send_ha_notification(
            service_name="notify.pushover",
            message="Hi",
            title="D",
        )
    path, _ = mock_post.call_args[0]
    assert path == "/services/notify/pushover"
