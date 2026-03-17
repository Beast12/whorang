"""Tests for HomeAssistantAPI.call_llmvision()."""
import os, sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def ha_api():
    from src.utils import HomeAssistantAPI
    return HomeAssistantAPI()


async def _make_post_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    return resp


@pytest.mark.asyncio
async def test_call_llmvision_returns_text_and_title(ha_api):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "service_response": {"response_text": "A tall stranger!", "title": "Visitor"}
    }
    with patch.object(ha_api, '_post', new=AsyncMock(return_value=mock_resp)):
        text, title = await ha_api.call_llmvision(
            image_file="/config/www/img.jpg",
            provider="openai",
            model="gpt-4o-mini",
            prompt="Describe",
            max_tokens=100,
        )
    assert text == "A tall stranger!"
    assert title == "Visitor"


@pytest.mark.asyncio
async def test_call_llmvision_request_body_shape(ha_api):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"service_response": {"response_text": "Hi"}}
    mock_post = AsyncMock(return_value=mock_resp)
    with patch.object(ha_api, '_post', new=mock_post):
        await ha_api.call_llmvision(
            image_file="/config/www/img.jpg",
            provider="openai",
            model="gpt-4o-mini",
            prompt="Describe",
            max_tokens=100,
        )
    path, body = mock_post.call_args[0]
    assert path == "/services/llmvision/image_analyzer"
    assert body["return_response"] is True
    assert body["image_file"] == "/config/www/img.jpg"
    assert body["provider"] == "openai"
    assert body["temperature"] == 0.2
    assert "generate_title" not in body


@pytest.mark.asyncio
async def test_call_llmvision_missing_title_falls_back_to_doorbell(ha_api):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"service_response": {"response_text": "Someone"}}
    with patch.object(ha_api, '_post', new=AsyncMock(return_value=mock_resp)):
        text, title = await ha_api.call_llmvision(
            image_file="/config/www/img.jpg",
            provider="openai",
            model="gpt-4o-mini",
            prompt="Describe",
            max_tokens=100,
        )
    assert title == "Doorbell"


@pytest.mark.asyncio
async def test_call_llmvision_post_failure_returns_default(ha_api):
    with patch.object(ha_api, '_post', new=AsyncMock(return_value=None)):
        with patch('src.utils.settings') as mock_settings:
            mock_settings.default_message = "Someone is at the door"
            text, title = await ha_api.call_llmvision(
                image_file="/config/www/img.jpg",
                provider="openai",
                model="gpt-4o-mini",
                prompt="Describe",
                max_tokens=100,
            )
    assert text == "Someone is at the door"
    assert title == "Doorbell"


@pytest.mark.asyncio
async def test_call_llmvision_missing_response_text_falls_back_to_default(ha_api):
    """service_response exists but has no response_text — fall back to default_message."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"service_response": {"title": "Visitor"}}
    with patch.object(ha_api, '_post', new=AsyncMock(return_value=mock_resp)):
        with patch('src.utils.settings') as mock_settings:
            mock_settings.default_message = "Someone is at the door"
            text, title = await ha_api.call_llmvision(
                image_file="/config/www/img.jpg",
                provider="openai",
                model="gpt-4o-mini",
                prompt="Describe",
                max_tokens=100,
            )
    assert text == "Someone is at the door"
    assert title == "Visitor"
