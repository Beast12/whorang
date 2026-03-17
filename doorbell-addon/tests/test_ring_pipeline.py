"""Tests for run_ring_pipeline()."""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _make_mocks(tmp_path, *, camera_ok=True, llm_enabled=True,
                provider="openai", public_path=None, notify_services=None):
    mock_settings = MagicMock()
    mock_settings.images_path = str(tmp_path / "images")
    mock_settings.face_recognition_enabled = False
    mock_settings.weather_entity = None
    mock_settings.llmvision_enabled = llm_enabled
    mock_settings.llmvision_provider = provider
    mock_settings.llmvision_model = "gpt-4o-mini"
    mock_settings.llmvision_prompt = "Describe"
    mock_settings.llmvision_max_tokens = 100
    mock_settings.default_message = "Someone is at the door"
    mock_settings.public_image_path = public_path
    mock_settings.ha_notify_services = notify_services or []
    mock_settings.notification_webhook = None

    mock_camera = MagicMock()
    if camera_ok:
        def fake_capture(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, 'wb').write(b"img")
            return True
        mock_camera.capture_image.side_effect = fake_capture
    else:
        mock_camera.capture_image.return_value = False

    mock_db = MagicMock()
    mock_db.add_doorbell_event.return_value = MagicMock(
        id=42, timestamp=MagicMock(isoformat=lambda: "2026-01-01T00:00:00")
    )
    mock_frs = MagicMock()
    mock_frs.is_ready.return_value = False
    mock_ha_integration = MagicMock()
    mock_ha_integration.handle_doorbell_ring = AsyncMock()
    mock_notification_manager = MagicMock()
    mock_notification_manager._send_webhook_notification = AsyncMock()
    return mock_settings, mock_camera, mock_db, mock_frs, mock_ha_integration, mock_notification_manager


@pytest.fixture
def pipeline_mod():
    import src.ring_pipeline as mod
    return mod


def _patch_pipeline(pipeline_mod, mock_settings, mock_camera, mock_db, mock_frs,
                    mock_ha_integration, mock_notification_manager):
    return [
        patch.object(pipeline_mod, 'settings', mock_settings),
        patch.object(pipeline_mod, 'ha_camera_manager', mock_camera),
        patch.object(pipeline_mod, 'db', mock_db),
        patch.object(pipeline_mod, 'face_recognition_service', mock_frs),
        patch.object(pipeline_mod, 'ha_integration', mock_ha_integration),
        patch.object(pipeline_mod, 'notification_manager', mock_notification_manager),
    ]


@pytest.mark.asyncio
async def test_returns_event_id_and_messages(tmp_path, pipeline_mod):
    mocks = _make_mocks(tmp_path)
    mock_settings = mocks[0]
    # Disable LLM so it uses default_message
    mock_settings.llmvision_enabled = False
    patches = _patch_pipeline(pipeline_mod, *mocks)
    for p in patches: p.start()
    try:
        result = await pipeline_mod.run_ring_pipeline()
    finally:
        for p in patches: p.stop()
    assert result["event_id"] == 42
    assert result["ai_message"] == "Someone is at the door"
    assert result["ai_title"] == "Doorbell"


@pytest.mark.asyncio
async def test_image_path_provided_skips_camera(tmp_path, pipeline_mod):
    snapshot = tmp_path / "snap.jpg"
    snapshot.write_bytes(b"JFIF")
    mocks = _make_mocks(tmp_path)
    mocks[0].llmvision_enabled = False
    patches = _patch_pipeline(pipeline_mod, *mocks)
    for p in patches: p.start()
    try:
        await pipeline_mod.run_ring_pipeline(image_path=str(snapshot))
    finally:
        for p in patches: p.stop()
    mocks[1].capture_image.assert_not_called()


@pytest.mark.asyncio
async def test_no_image_path_uses_camera(tmp_path, pipeline_mod):
    mocks = _make_mocks(tmp_path)
    mocks[0].llmvision_enabled = False
    patches = _patch_pipeline(pipeline_mod, *mocks)
    for p in patches: p.start()
    try:
        await pipeline_mod.run_ring_pipeline()
    finally:
        for p in patches: p.stop()
    mocks[1].capture_image.assert_called_once()


@pytest.mark.asyncio
async def test_caller_provided_ai_message_skips_llm(tmp_path, pipeline_mod):
    mocks = _make_mocks(tmp_path, public_path=str(tmp_path / "www"))
    mock_ha_api = MagicMock()
    mock_ha_api.call_llmvision = AsyncMock()
    patches = _patch_pipeline(pipeline_mod, *mocks)
    for p in patches: p.start()
    with patch.object(pipeline_mod, 'HomeAssistantAPI', return_value=mock_ha_api):
        result = await pipeline_mod.run_ring_pipeline(ai_message="Custom!")
    for p in patches: p.stop()
    mock_ha_api.call_llmvision.assert_not_called()
    assert result["ai_message"] == "Custom!"
    assert result["ai_title"] == "Doorbell"


@pytest.mark.asyncio
async def test_llm_disabled_uses_default_message(tmp_path, pipeline_mod):
    mocks = _make_mocks(tmp_path, llm_enabled=False)
    mock_ha_api = MagicMock()
    mock_ha_api.call_llmvision = AsyncMock()
    patches = _patch_pipeline(pipeline_mod, *mocks)
    for p in patches: p.start()
    with patch.object(pipeline_mod, 'HomeAssistantAPI', return_value=mock_ha_api):
        result = await pipeline_mod.run_ring_pipeline()
    for p in patches: p.stop()
    mock_ha_api.call_llmvision.assert_not_called()
    assert result["ai_message"] == "Someone is at the door"


@pytest.mark.asyncio
async def test_llm_no_provider_uses_default_message(tmp_path, pipeline_mod):
    mocks = _make_mocks(tmp_path, provider=None, public_path=str(tmp_path / "www"))
    mock_ha_api = MagicMock()
    mock_ha_api.call_llmvision = AsyncMock()
    patches = _patch_pipeline(pipeline_mod, *mocks)
    for p in patches: p.start()
    with patch.object(pipeline_mod, 'HomeAssistantAPI', return_value=mock_ha_api):
        await pipeline_mod.run_ring_pipeline()
    for p in patches: p.stop()
    mock_ha_api.call_llmvision.assert_not_called()


@pytest.mark.asyncio
async def test_llm_no_public_path_uses_default_message(tmp_path, pipeline_mod):
    mocks = _make_mocks(tmp_path, public_path=None)
    mock_ha_api = MagicMock()
    mock_ha_api.call_llmvision = AsyncMock()
    patches = _patch_pipeline(pipeline_mod, *mocks)
    for p in patches: p.start()
    with patch.object(pipeline_mod, 'HomeAssistantAPI', return_value=mock_ha_api):
        await pipeline_mod.run_ring_pipeline()
    for p in patches: p.stop()
    mock_ha_api.call_llmvision.assert_not_called()


@pytest.mark.asyncio
async def test_ha_notifications_sent_for_each_service(tmp_path, pipeline_mod):
    mocks = _make_mocks(tmp_path, llm_enabled=False,
                        notify_services=["notify.mobile_app_phone", "notify.telegram_bot"])
    mock_ha_api = MagicMock()
    mock_ha_api.send_ha_notification = AsyncMock()
    patches = _patch_pipeline(pipeline_mod, *mocks)
    for p in patches: p.start()
    with patch.object(pipeline_mod, 'HomeAssistantAPI', return_value=mock_ha_api):
        await pipeline_mod.run_ring_pipeline()
    for p in patches: p.stop()
    assert mock_ha_api.send_ha_notification.call_count == 2


@pytest.mark.asyncio
async def test_event_saved_to_db(tmp_path, pipeline_mod):
    mocks = _make_mocks(tmp_path, llm_enabled=False)
    patches = _patch_pipeline(pipeline_mod, *mocks)
    for p in patches: p.start()
    try:
        await pipeline_mod.run_ring_pipeline()
    finally:
        for p in patches: p.stop()
    mocks[2].add_doorbell_event.assert_called_once()


@pytest.mark.asyncio
async def test_ha_integration_called(tmp_path, pipeline_mod):
    mocks = _make_mocks(tmp_path, llm_enabled=False)
    patches = _patch_pipeline(pipeline_mod, *mocks)
    for p in patches: p.start()
    try:
        await pipeline_mod.run_ring_pipeline()
    finally:
        for p in patches: p.stop()
    mocks[4].handle_doorbell_ring.assert_called_once()


@pytest.mark.asyncio
async def test_public_image_write_failure_skips_llm(tmp_path, pipeline_mod):
    """If writing the public copy fails, LLM is skipped (no public_filename)."""
    mocks = _make_mocks(tmp_path, public_path=str(tmp_path / "www"))
    mock_ha_api = MagicMock()
    mock_ha_api.call_llmvision = AsyncMock()
    patches = _patch_pipeline(pipeline_mod, *mocks)
    for p in patches: p.start()
    with patch.object(pipeline_mod, 'HomeAssistantAPI', return_value=mock_ha_api), \
         patch('shutil.copy2', side_effect=OSError("disk full")):
        result = await pipeline_mod.run_ring_pipeline()
    for p in patches: p.stop()
    # LLM was not called because public copy failed → public_filename is None
    mock_ha_api.call_llmvision.assert_not_called()
    assert result["ai_message"] == "Someone is at the door"
