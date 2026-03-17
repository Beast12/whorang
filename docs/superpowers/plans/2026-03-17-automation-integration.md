# Automation Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move all ring-event logic (LLM description, HA push notifications, public image mirroring) out of HA automations into the addon, reducing the user's HA automation to a single trigger → REST call with no logic.

**Architecture:** A new `ring_pipeline.py` module owns the complete ring flow as `run_ring_pipeline(image_path, ai_message) -> dict`. Two new helpers (`call_llmvision`, `send_ha_notification`) are added to `HomeAssistantAPI` in `utils.py`. The `app.py` ring handler becomes a thin wrapper that delegates to the pipeline. Seven new settings fields are added to `config.py` and persisted to `settings.json`. The Settings page gets four new cards backed by two new discovery API endpoints.

**Tech Stack:** Python 3.11, FastAPI, asyncio, httpx, SQLite, Jinja2, vanilla JS, Bootstrap 5 (existing stack — no new dependencies)

**Spec:** `docs/superpowers/specs/2026-03-17-automation-integration-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `doorbell-addon/src/ring_pipeline.py` | Create | `run_ring_pipeline()` — 7-step ring flow |
| `doorbell-addon/src/utils.py` | Modify | Add `classify_notify_service()`, `call_llmvision()`, `send_ha_notification()` |
| `doorbell-addon/src/config.py` | Modify | 7 new settings fields + `_PERSISTED_FIELDS` update |
| `doorbell-addon/src/app.py` | Modify | Thin ring handler + 2 discovery endpoints + settings GET/POST for new fields |
| `doorbell-addon/web/templates/settings.html` | Modify | 4 new settings cards (AI Description, HA Push, Public Image, Trigger Helper) |
| `doorbell-addon/web/static/js/settings.js` | Modify | Notify checklist, binary sensor dropdown, YAML copy, AI settings save |
| `doorbell-addon/config.yaml` | Modify | `config:ro` → `config:rw` (write access to `/config/www`) |
| `doorbell-addon/tests/test_utils_llmvision.py` | Create | Tests for `call_llmvision()` |
| `doorbell-addon/tests/test_utils_notify.py` | Create | Tests for `classify_notify_service()` + `send_ha_notification()` |
| `doorbell-addon/tests/test_ring_pipeline.py` | Create | Tests for `run_ring_pipeline()` |
| `doorbell-addon/tests/test_settings_api_discovery.py` | Create | Tests for the two discovery endpoints |
| `doorbell-addon/tests/test_ring_image_path.py` | Modify | Update to test thin handler (mock `run_ring_pipeline`) |

---

## Task 1: New settings fields in `config.py`

**Files:**
- Modify: `doorbell-addon/src/config.py`

**Background:** Settings are `pydantic_settings.BaseSettings` fields. New fields must be added to the class and to `_PERSISTED_FIELDS` so they round-trip to `settings.json`. The `load_from_file()` / `save_to_file()` methods handle the JSON persistence automatically.

- [ ] **Step 1: Write failing test**

  Create `doorbell-addon/tests/test_config_new_fields.py`:

  ```python
  """Tests for new automation-integration settings fields."""
  import json, os, sys
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
  ```

- [ ] **Step 2: Run test to verify it fails**

  ```bash
  cd doorbell-addon && python -m pytest tests/test_config_new_fields.py -v
  ```

  Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'llmvision_enabled'`

- [ ] **Step 3: Add fields to `config.py`**

  In `doorbell-addon/src/config.py`, add after the `weather_entity` field (line ~25):

  ```python
      # AI description (llmvision)
      llmvision_enabled: bool = os.getenv("LLMVISION_ENABLED", "false").lower() == "true"
      llmvision_provider: Optional[str] = os.getenv("LLMVISION_PROVIDER")
      llmvision_model: str = os.getenv("LLMVISION_MODEL", "gpt-4o-mini")
      llmvision_prompt: str = os.getenv(
          "LLMVISION_PROMPT",
          "You are my sarcastic funny security guard. Describe what you see in one funny "
          "one-liner of max 10 words. Only describe the person, vehicle or animal.",
      )
      llmvision_max_tokens: int = int(os.getenv("LLMVISION_MAX_TOKENS", "100"))
      default_message: str = os.getenv("DEFAULT_MESSAGE", "Someone is at the door")

      # HA push notifications
      ha_notify_services: list = []   # persisted only — no env var default

      # Public image mirror
      public_image_path: Optional[str] = os.getenv("PUBLIC_IMAGE_PATH")

      # Trigger helper (display only)
      trigger_entity: Optional[str] = os.getenv("TRIGGER_ENTITY")
  ```

  Then extend `_PERSISTED_FIELDS` tuple to include the new fields (add to the existing tuple):

  ```python
      _PERSISTED_FIELDS: ClassVar[tuple] = (
          "camera_url",
          "camera_entity",
          "ha_access_token",
          "weather_entity",
          "notification_webhook",
          "retention_days",
          "storage_path",
          "face_recognition_enabled",
          "face_recognition_model",
          "face_recognition_threshold",
          # automation integration
          "llmvision_enabled",
          "llmvision_provider",
          "llmvision_model",
          "llmvision_prompt",
          "llmvision_max_tokens",
          "default_message",
          "ha_notify_services",
          "public_image_path",
          "trigger_entity",
      )
  ```

- [ ] **Step 4: Run test to verify it passes**

  ```bash
  cd doorbell-addon && python -m pytest tests/test_config_new_fields.py -v
  ```

  Expected: PASS (2 tests)

- [ ] **Step 5: Run existing config tests**

  ```bash
  cd doorbell-addon && python -m pytest tests/test_config_utils.py -v
  ```

  Expected: All pass (no regressions)

- [ ] **Step 6: Commit**

  ```bash
  git add doorbell-addon/src/config.py doorbell-addon/tests/test_config_new_fields.py
  git commit -m "feat: add automation integration settings fields to config"
  ```

---

## Task 2: `classify_notify_service()` and `call_llmvision()` in `utils.py`

**Files:**
- Modify: `doorbell-addon/src/utils.py`
- Create: `doorbell-addon/tests/test_utils_llmvision.py`

**Background:** `HomeAssistantAPI._post(path, json)` already handles auth headers and a 10 s timeout. `call_llmvision` builds on it. The `classify_notify_service` module-level function is kept outside the class so `ring_pipeline.py` can import it without a class instance.

- [ ] **Step 1: Write failing tests**

  Create `doorbell-addon/tests/test_utils_llmvision.py`:

  ```python
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
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  cd doorbell-addon && python -m pytest tests/test_utils_llmvision.py -v
  ```

  Expected: FAIL — `AttributeError: 'HomeAssistantAPI' object has no attribute 'call_llmvision'`

- [ ] **Step 3: Add `classify_notify_service` and `call_llmvision` to `utils.py`**

  Add this module-level constant and function **before** the `HomeAssistantAPI` class definition (after the `logger` line):

  ```python
  _AUDIO_ONLY_PREFIXES = ("tts_", "alexa_media_", "google_")
  _IMAGE_CAPABLE_PREFIXES = ("mobile_app_", "telegram_", "html5_")


  def classify_notify_service(name: str) -> str:
      """Classify a notify service name (without domain prefix).

      Returns 'image' (rich payload with image URL), 'audio' (message only),
      or 'full' (full payload, HA may ignore unsupported data fields).
      """
      for prefix in _IMAGE_CAPABLE_PREFIXES:
          if name.startswith(prefix):
              return "image"
      for prefix in _AUDIO_ONLY_PREFIXES:
          if name.startswith(prefix):
              return "audio"
      return "full"
  ```

  Add `call_llmvision` method to `HomeAssistantAPI` after the `get_weather_data` method:

  ```python
      async def call_llmvision(
          self,
          image_file: str,
          provider: str,
          model: str,
          prompt: str,
          max_tokens: int,
      ) -> tuple:
          """Call llmvision.image_analyzer via the supervisor API.

          Returns (response_text, title). Falls back to (default_message, "Doorbell")
          when the call fails or the response is malformed. Timeout is 10 s (set in _post).
          """
          response = await self._post(
              "/services/llmvision/image_analyzer",
              {
                  "return_response": True,
                  "provider": provider,
                  "model": model,
                  "message": prompt,
                  "image_file": image_file,
                  "max_tokens": max_tokens,
                  "temperature": 0.2,
              },
          )
          if not response:
              return settings.default_message, "Doorbell"
          svc = response.json().get("service_response", {})
          text = svc.get("response_text") or settings.default_message
          title = svc.get("title") or "Doorbell"
          return text, title
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  cd doorbell-addon && python -m pytest tests/test_utils_llmvision.py -v
  ```

  Expected: 4 tests PASS

- [ ] **Step 5: Commit**

  ```bash
  git add doorbell-addon/src/utils.py doorbell-addon/tests/test_utils_llmvision.py
  git commit -m "feat: add classify_notify_service and call_llmvision to utils"
  ```

---

## Task 3: `send_ha_notification()` in `utils.py`

**Files:**
- Modify: `doorbell-addon/src/utils.py`
- Create: `doorbell-addon/tests/test_utils_notify.py`

**Background:** `send_ha_notification` is a new method on `HomeAssistantAPI`. It strips the `notify.` prefix from the service name, classifies it with `classify_notify_service`, builds the payload, and calls `_post`. The `data.image` field uses `/local/<filename>` — HA's convention for files in `/config/www`. It is omitted if `image_filename` is `None`.

- [ ] **Step 1: Write failing tests**

  Create `doorbell-addon/tests/test_utils_notify.py`:

  ```python
  """Tests for classify_notify_service() and HomeAssistantAPI.send_ha_notification()."""
  import os, sys
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
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  cd doorbell-addon && python -m pytest tests/test_utils_notify.py -v
  ```

  Expected: FAIL — `AttributeError: 'HomeAssistantAPI' object has no attribute 'send_ha_notification'`

  (The `classify_notify_service` tests may already pass from Task 2.)

- [ ] **Step 3: Add `send_ha_notification` to `HomeAssistantAPI` in `utils.py`**

  Add after the `call_llmvision` method:

  ```python
      async def send_ha_notification(
          self,
          service_name: str,
          message: str,
          title: str,
          image_filename: Optional[str] = None,
      ) -> None:
          """Send a notification to a specific HA notify service.

          Payload is tailored to service type: audio-only services get message only;
          image-capable and unknown services get title + message + optional data.image.
          service_name must be the full name e.g. 'notify.mobile_app_phone'.
          """
          suffix = service_name.removeprefix("notify.")
          kind = classify_notify_service(suffix)
          if kind == "audio":
              payload: Dict = {"message": message}
          else:
              payload = {"title": title, "message": message}
              if image_filename:
                  payload["data"] = {
                      "image": f"/local/{image_filename}",
                      "ttl": 0,
                      "priority": "high",
                  }
          await self._post(f"/services/notify/{suffix}", payload)
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  cd doorbell-addon && python -m pytest tests/test_utils_notify.py -v
  ```

  Expected: 11 tests PASS

- [ ] **Step 5: Run all utils-related tests**

  ```bash
  cd doorbell-addon && python -m pytest tests/test_utils_llmvision.py tests/test_utils_notify.py -v
  ```

  Expected: 15 tests PASS

- [ ] **Step 6: Commit**

  ```bash
  git add doorbell-addon/src/utils.py doorbell-addon/tests/test_utils_notify.py
  git commit -m "feat: add send_ha_notification to HomeAssistantAPI"
  ```

---

## Task 4: `ring_pipeline.py` — new module

**Files:**
- Create: `doorbell-addon/src/ring_pipeline.py`
- Create: `doorbell-addon/tests/test_ring_pipeline.py`

**Background:** This is the core of the feature. The function runs 7 steps sequentially (step 2 is awaited before step 3), with all degradable steps using `asyncio.gather(return_exceptions=True)`. The existing `test_ring_image_path.py` tests the image-copy behavior which now lives in this module — the new `test_ring_pipeline.py` covers it properly.

- [ ] **Step 1: Write failing tests**

  Create `doorbell-addon/tests/test_ring_pipeline.py`:

  ```python
  """Tests for run_ring_pipeline()."""
  import asyncio, json, os, sys
  import pytest
  from unittest.mock import AsyncMock, MagicMock, patch, call
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
          result = await pipeline_mod.run_ring_pipeline()
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
          result = await pipeline_mod.run_ring_pipeline()
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
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  cd doorbell-addon && python -m pytest tests/test_ring_pipeline.py -v
  ```

  Expected: FAIL — `ModuleNotFoundError: No module named 'src.ring_pipeline'`

- [ ] **Step 3: Create `doorbell-addon/src/ring_pipeline.py`**

  ```python
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
  from .utils import HomeAssistantAPI, notification_manager

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
              return ai_message, "Doorbell"
          if not (
              settings.llmvision_enabled
              and settings.llmvision_provider
              and settings.public_image_path
              and public_filename
          ):
              return settings.default_message, "Doorbell"
          ha_api = HomeAssistantAPI()
          try:
              return await ha_api.call_llmvision(
                  image_file=os.path.join(settings.public_image_path, public_filename),
                  provider=settings.llmvision_provider,
                  model=settings.llmvision_model,
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
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  cd doorbell-addon && python -m pytest tests/test_ring_pipeline.py -v
  ```

  Expected: 10 tests PASS

- [ ] **Step 5: Commit**

  ```bash
  git add doorbell-addon/src/ring_pipeline.py doorbell-addon/tests/test_ring_pipeline.py
  git commit -m "feat: add ring_pipeline module with run_ring_pipeline"
  ```

---

## Task 5: Thin ring handler + settings endpoints in `app.py`

**Files:**
- Modify: `doorbell-addon/src/app.py`
- Modify: `doorbell-addon/tests/test_ring_image_path.py`
- Create: `doorbell-addon/tests/test_settings_api_discovery.py`

**Background:** The ring handler delegates entirely to `run_ring_pipeline`. The `test_ring_image_path.py` tests must be updated — they now mock `run_ring_pipeline` directly rather than `db`, `camera`, etc. Two new discovery endpoints for the settings UI are added. The settings `GET` and `POST` endpoints are updated to include the new fields.

- [ ] **Step 1: Update `test_ring_image_path.py` to mock the pipeline**

  Replace the entire file content:

  ```python
  """Tests for ring endpoint — thin handler delegates to run_ring_pipeline."""
  import os, sys
  import pytest
  from unittest.mock import patch, AsyncMock, MagicMock
  sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

  _real_staticfiles_init = None


  def _patched_staticfiles_init(self, **kwargs):
      kwargs["check_dir"] = False
      _real_staticfiles_init(self, **kwargs)


  def _patch_app_imports():
      global _real_staticfiles_init
      from starlette.staticfiles import StaticFiles
      if _real_staticfiles_init is None:
          _real_staticfiles_init = StaticFiles.__init__
          StaticFiles.__init__ = _patched_staticfiles_init


  _patch_app_imports()


  @pytest.fixture
  def client():
      from fastapi.testclient import TestClient
      import src.app as app_mod
      mock_ha_integration = MagicMock()
      mock_ha_integration.initialize = AsyncMock()
      with patch.object(app_mod, 'ha_integration', mock_ha_integration), \
           patch.object(app_mod, 'ensure_directories', MagicMock()):
          with TestClient(app_mod.app, raise_server_exceptions=True) as c:
              yield c


  def test_ring_returns_success_response(client):
      """Ring handler returns all required fields."""
      mock_result = {"event_id": 7, "ai_message": "Hi!", "ai_title": "Doorbell"}
      with patch('src.app.run_ring_pipeline', new=AsyncMock(return_value=mock_result)):
          resp = client.post("/api/doorbell/ring", data={})
      assert resp.status_code == 200
      body = resp.json()
      assert body["success"] is True
      assert body["event_id"] == 7
      assert body["ai_message"] == "Hi!"
      assert body["ai_title"] == "Doorbell"
      assert "timestamp" in body
      assert body["message"] == "Doorbell ring processed"


  def test_ring_passes_image_path_to_pipeline(client):
      """image_path form field is forwarded to run_ring_pipeline."""
      mock_result = {"event_id": 1, "ai_message": "Test", "ai_title": "Doorbell"}
      mock_pipeline = AsyncMock(return_value=mock_result)
      with patch('src.app.run_ring_pipeline', new=mock_pipeline):
          client.post("/api/doorbell/ring", data={"image_path": "/some/path.jpg"})
      mock_pipeline.assert_called_once()
      assert mock_pipeline.call_args.kwargs["image_path"] == "/some/path.jpg"


  def test_ring_passes_ai_message_to_pipeline(client):
      """ai_message form field is forwarded to run_ring_pipeline."""
      mock_result = {"event_id": 1, "ai_message": "Custom", "ai_title": "Doorbell"}
      mock_pipeline = AsyncMock(return_value=mock_result)
      with patch('src.app.run_ring_pipeline', new=mock_pipeline):
          client.post("/api/doorbell/ring", data={"ai_message": "Custom"})
      assert mock_pipeline.call_args.kwargs["ai_message"] == "Custom"


  def test_ring_pipeline_error_returns_500(client):
      """RuntimeError from pipeline becomes HTTP 500."""
      with patch('src.app.run_ring_pipeline', new=AsyncMock(side_effect=RuntimeError("Camera fail"))):
          resp = client.post("/api/doorbell/ring", data={})
      assert resp.status_code == 500
  ```

- [ ] **Step 2: Write failing discovery endpoint tests**

  Create `doorbell-addon/tests/test_settings_api_discovery.py`:

  ```python
  """Tests for GET /api/settings/notify-services and /api/settings/binary-sensors."""
  import os, sys
  import pytest
  from unittest.mock import patch, AsyncMock, MagicMock
  sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

  _real_staticfiles_init = None


  def _patched_staticfiles_init(self, **kwargs):
      kwargs["check_dir"] = False
      _real_staticfiles_init(self, **kwargs)


  def _patch_app_imports():
      global _real_staticfiles_init
      from starlette.staticfiles import StaticFiles
      if _real_staticfiles_init is None:
          _real_staticfiles_init = StaticFiles.__init__
          StaticFiles.__init__ = _patched_staticfiles_init


  _patch_app_imports()


  @pytest.fixture
  def client():
      from fastapi.testclient import TestClient
      import src.app as app_mod
      mock_ha_integration = MagicMock()
      mock_ha_integration.initialize = AsyncMock()
      with patch.object(app_mod, 'ha_integration', mock_ha_integration), \
           patch.object(app_mod, 'ensure_directories', MagicMock()):
          with TestClient(app_mod.app, raise_server_exceptions=True) as c:
              yield c


  def _mock_ha_api_get(return_value):
      """Return an AsyncMock for HomeAssistantAPI._get with a given JSON response."""
      mock_resp = MagicMock()
      mock_resp.json.return_value = return_value
      mock_api = MagicMock()
      mock_api._get = AsyncMock(return_value=mock_resp)
      return mock_api


  def test_notify_services_filters_and_classifies(client):
      ha_services_response = [
          {"domain": "notify", "services": {"mobile_app_phone": {}, "tts_kitchen": {}, "pushover": {}}},
          {"domain": "light", "services": {"turn_on": {}}},
      ]
      mock_api = _mock_ha_api_get(ha_services_response)
      with patch('src.app.HomeAssistantAPI', return_value=mock_api):
          resp = client.get("/api/settings/notify-services")
      assert resp.status_code == 200
      svcs = {s["name"]: s for s in resp.json()["services"]}
      assert "notify.mobile_app_phone" in svcs
      assert svcs["notify.mobile_app_phone"]["image_capable"] is True
      assert svcs["notify.tts_kitchen"]["image_capable"] is False
      assert "notify.light" not in svcs


  def test_notify_services_returns_empty_on_api_failure(client):
      mock_api = MagicMock()
      mock_api._get = AsyncMock(return_value=None)
      with patch('src.app.HomeAssistantAPI', return_value=mock_api):
          resp = client.get("/api/settings/notify-services")
      assert resp.status_code == 200
      assert resp.json()["services"] == []


  def test_binary_sensors_filters_entity_ids(client):
      states = [
          {"entity_id": "binary_sensor.doorbell", "attributes": {"friendly_name": "Doorbell"}},
          {"entity_id": "binary_sensor.motion", "attributes": {}},
          {"entity_id": "sensor.temperature", "attributes": {}},
      ]
      mock_api = _mock_ha_api_get(states)
      with patch('src.app.HomeAssistantAPI', return_value=mock_api):
          resp = client.get("/api/settings/binary-sensors")
      assert resp.status_code == 200
      entities = resp.json()["entities"]
      ids = [e["entity_id"] for e in entities]
      assert "binary_sensor.doorbell" in ids
      assert "binary_sensor.motion" in ids
      assert "sensor.temperature" not in ids


  def test_binary_sensors_returns_empty_on_api_failure(client):
      mock_api = MagicMock()
      mock_api._get = AsyncMock(return_value=None)
      with patch('src.app.HomeAssistantAPI', return_value=mock_api):
          resp = client.get("/api/settings/binary-sensors")
      assert resp.status_code == 200
      assert resp.json()["entities"] == []
  ```

- [ ] **Step 3: Run tests to verify they fail**

  ```bash
  cd doorbell-addon && python -m pytest tests/test_ring_image_path.py tests/test_settings_api_discovery.py -v
  ```

  Expected: `test_ring_image_path.py` — import error (no `run_ring_pipeline` in `app`); `test_settings_api_discovery.py` — 404 on discovery endpoints.

- [ ] **Step 4: Modify `app.py`**

  **4a — Add import at the top** (after the existing `.utils` import block):

  ```python
  from .ring_pipeline import run_ring_pipeline
  from .utils import HomeAssistantAPI, classify_notify_service, ...
  ```

  Make sure `classify_notify_service` is included in the existing `from .utils import ...` line.

  **4b — Replace the entire `doorbell_ring` handler** (lines 338–459 in the current file):

  ```python
  @app.post("/api/doorbell/ring")
  async def doorbell_ring(
      ai_message: Optional[str] = Form(None),
      image_path: Optional[str] = Form(None),
  ):
      """Handle a doorbell ring event — capture image, run pipeline, return result."""
      logger.info("Doorbell ring event received", ai_message=ai_message)
      try:
          result = await run_ring_pipeline(image_path=image_path, ai_message=ai_message)
          return {
              "success": True,
              "message": "Doorbell ring processed",
              "timestamp": datetime.now().isoformat(),
              "event_id": result["event_id"],
              "ai_message": result["ai_message"],
              "ai_title": result["ai_title"],
          }
      except HTTPException:
          raise
      except Exception as e:
          logger.error("Error processing doorbell ring", error=str(e))
          raise HTTPException(status_code=500, detail=f"Doorbell processing failed: {str(e)}")
  ```

  **4c — Add discovery endpoints** (add after `get_available_weather_entities`):

  ```python
  @app.get("/api/settings/notify-services")
  async def get_notify_services():
      """Fetch and classify notify.* services from HA. Returns empty list on failure."""
      try:
          ha_api = HomeAssistantAPI()
          response = await ha_api._get("/services")
          if not response:
              return {"services": []}
          domains = {d["domain"]: d["services"] for d in response.json()}
          notify_svcs = domains.get("notify", {})
          result = [
              {
                  "name": f"notify.{name}",
                  "image_capable": classify_notify_service(name) in ("image", "full"),
                  "classification": classify_notify_service(name),
              }
              for name in notify_svcs
          ]
          return {"services": result}
      except Exception as e:
          logger.warning("Failed to fetch notify services", error=str(e))
          return {"services": []}


  @app.get("/api/settings/binary-sensors")
  async def get_binary_sensors():
      """Fetch binary_sensor.* entities from HA. Returns empty list on failure."""
      try:
          ha_api = HomeAssistantAPI()
          response = await ha_api._get("/states")
          if not response:
              return {"entities": []}
          entities = [
              {
                  "entity_id": s["entity_id"],
                  "friendly_name": s.get("attributes", {}).get("friendly_name", s["entity_id"]),
              }
              for s in response.json()
              if s.get("entity_id", "").startswith("binary_sensor.")
          ]
          return {"entities": entities}
      except Exception as e:
          logger.warning("Failed to fetch binary sensors", error=str(e))
          return {"entities": []}
  ```

  **4d — Update `GET /api/settings`** to include new fields (add to the returned dict):

  ```python
      return {
          # ... existing fields ...
          "llmvision_enabled": settings.llmvision_enabled,
          "llmvision_provider": settings.llmvision_provider,
          "llmvision_model": settings.llmvision_model,
          "llmvision_prompt": settings.llmvision_prompt,
          "llmvision_max_tokens": settings.llmvision_max_tokens,
          "default_message": settings.default_message,
          "ha_notify_services": settings.ha_notify_services,
          "public_image_path": settings.public_image_path,
          "trigger_entity": settings.trigger_entity,
      }
  ```

  **4e — Update `POST /api/settings`** to handle new fields (add inside the `if` chain):

  ```python
          if "llmvision_enabled" in data:
              settings.llmvision_enabled = bool(data["llmvision_enabled"])
          if "llmvision_provider" in data:
              settings.llmvision_provider = data["llmvision_provider"] or None
          if "llmvision_model" in data:
              settings.llmvision_model = data["llmvision_model"]
          if "llmvision_prompt" in data:
              settings.llmvision_prompt = data["llmvision_prompt"]
          if "llmvision_max_tokens" in data:
              settings.llmvision_max_tokens = int(data["llmvision_max_tokens"])
          if "default_message" in data:
              settings.default_message = data["default_message"]
          if "ha_notify_services" in data:
              settings.ha_notify_services = list(data["ha_notify_services"])
          if "public_image_path" in data:
              settings.public_image_path = data["public_image_path"] or None
          if "trigger_entity" in data:
              settings.trigger_entity = data["trigger_entity"] or None
  ```

- [ ] **Step 5: Run tests**

  ```bash
  cd doorbell-addon && python -m pytest tests/test_ring_image_path.py tests/test_settings_api_discovery.py -v
  ```

  Expected: 8 tests PASS

- [ ] **Step 6: Run full test suite**

  ```bash
  cd doorbell-addon && python -m pytest tests/ -v
  ```

  Expected: All pass (no regressions)

- [ ] **Step 7: Run linter**

  ```bash
  cd doorbell-addon && flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics
  ```

  Expected: 0 errors

- [ ] **Step 8: Commit**

  ```bash
  git add doorbell-addon/src/app.py doorbell-addon/tests/test_ring_image_path.py doorbell-addon/tests/test_settings_api_discovery.py
  git commit -m "feat: thin ring handler delegates to pipeline; add discovery API endpoints"
  ```

---

## Task 6: Settings HTML — four new cards

**Files:**
- Modify: `doorbell-addon/web/templates/settings.html`

**Background:** The existing settings.html has ~472 lines. Four new cards are added:
1. **AI Description** — after the Weather card, in the left column
2. **Notifications** card is updated — split into HA Push sub-section (new) + Webhook sub-section (existing)
3. **Public Image** — in the Storage section (right column)
4. **Trigger Helper** — in the Home Assistant section (right column)

The JS functions called from these cards (`saveAiDescription`, `loadNotifyServices`, `saveNotifications`, `savePublicImagePath`, `saveTriggerEntity`, `copyAutomationYaml`) are implemented in Task 7.

**There is no automated test for HTML — verify visually in browser after Task 7.**

- [ ] **Step 1: Add AI Description card**

  In `settings.html`, after the closing `</div>` of the Weather card (search for `id="weather-entity"` to find its location), add:

  ```html
  <!-- AI Description -->
  <div class="card mb-4" id="ai-description-card">
      <div class="card-header">
          <h5><i class="bi bi-stars"></i> AI Description</h5>
      </div>
      <div class="card-body">
          <div class="form-check form-switch mb-3">
              <input class="form-check-input" type="checkbox" id="llmvision-enabled"
                  {% if settings.llmvision_enabled %}checked{% endif %}>
              <label class="form-check-label" for="llmvision-enabled">Enable AI-generated description</label>
          </div>
          <div id="llmvision-fields">
              <div class="mb-3">
                  <label for="llmvision-provider" class="form-label">Provider ID</label>
                  <input type="text" class="form-control font-mono" id="llmvision-provider"
                      value="{{ settings.llmvision_provider or '' }}"
                      placeholder="e.g. openai">
                  <div class="form-text">The llmvision provider configured in your HA integration</div>
              </div>
              <div class="mb-3">
                  <label for="llmvision-model" class="form-label">Model</label>
                  <input type="text" class="form-control font-mono" id="llmvision-model"
                      value="{{ settings.llmvision_model }}">
              </div>
              <div class="mb-3">
                  <label for="llmvision-prompt" class="form-label">Prompt</label>
                  <textarea class="form-control font-mono" id="llmvision-prompt" rows="3">{{ settings.llmvision_prompt }}</textarea>
              </div>
              <div class="mb-3">
                  <label for="llmvision-max-tokens" class="form-label">
                      Max tokens: <span id="max-tokens-display">{{ settings.llmvision_max_tokens }}</span>
                  </label>
                  <input type="range" class="form-range" id="llmvision-max-tokens"
                      min="50" max="200" step="10"
                      value="{{ settings.llmvision_max_tokens }}"
                      oninput="document.getElementById('max-tokens-display').textContent=this.value">
              </div>
          </div>
          <div class="mb-3">
              <label for="default-message" class="form-label">Default message</label>
              <input type="text" class="form-control" id="default-message"
                  value="{{ settings.default_message }}">
              <div class="form-text">Used when AI is disabled or fails</div>
          </div>
          <div id="ai-public-path-warning" class="alert alert-warning py-1 px-2 small mb-3"
              style="display:none">
              AI description requires <strong>Public Image Path</strong> to be set.
          </div>
          <button class="btn btn-primary btn-sm" onclick="saveAiDescription()">Save</button>
      </div>
  </div>
  ```

- [ ] **Step 2: Update Notifications card**

  Find the existing Notifications card (search for `webhook-url`). Replace its content so it has two sub-sections. Keep the existing webhook fields, add HA Push above it:

  ```html
  <!-- Notifications -->
  <div class="card mb-4">
      <div class="card-header">
          <h5><i class="bi bi-bell-fill"></i> Notifications</h5>
      </div>
      <div class="card-body">
          <div class="wr-section-label">HA Push</div>
          <p class="form-text mb-2">Select which HA notify services receive a push notification on each ring.</p>
          <div id="notify-services-list" class="mb-2">
              <span class="text-muted small">Loading…</span>
          </div>
          <button class="btn btn-outline-secondary btn-sm mb-3" onclick="loadNotifyServices()">
              <i class="bi bi-arrow-clockwise"></i> Refresh
          </button>

          <div class="wr-section-label mt-2">Webhook / Gotify</div>
          <div class="mb-3">
              <label for="webhook-url" class="form-label">Webhook URL</label>
              <input type="text" class="form-control font-mono" id="webhook-url"
                  value="{{ settings.notification_webhook or '' }}"
                  placeholder="https://your-gotify-server/message?token=...">
              <div class="form-text">Optional. Also supports generic POST webhooks.</div>
          </div>

          <button class="btn btn-primary btn-sm" onclick="saveNotifications()">Save</button>
      </div>
  </div>
  ```

- [ ] **Step 3: Add Public Image card to the Storage section**

  The right column contains a Storage card. After the existing storage card's closing `</div>`, add:

  ```html
  <!-- Public Image -->
  <div class="card mb-4">
      <div class="card-header">
          <h5><i class="bi bi-folder-fill"></i> Public Image</h5>
      </div>
      <div class="card-body">
          <div class="mb-3">
              <label for="public-image-path" class="form-label">Public image directory</label>
              <input type="text" class="form-control font-mono" id="public-image-path"
                  value="{{ settings.public_image_path or '' }}"
                  placeholder="/config/www">
              <div class="form-text">
                  Images in this directory are served by HA at <code>/local/&lt;filename&gt;</code>.
                  Path must be under <code>/config/www</code> for HA to serve them.
                  Required for AI description and image notifications.
              </div>
          </div>
          <button class="btn btn-primary btn-sm" onclick="savePublicImagePath()">Save</button>
      </div>
  </div>
  ```

- [ ] **Step 4: Add Trigger Helper card to the Home Assistant section**

  After the HA section's existing content (or as its own card), add:

  ```html
  <!-- Trigger Helper -->
  <div class="card mb-4">
      <div class="card-header">
          <h5><i class="bi bi-lightning-charge-fill"></i> Trigger Helper</h5>
      </div>
      <div class="card-body">
          <p class="form-text mb-2">
              Select your doorbell binary sensor to generate a ready-to-paste HA automation.
          </p>
          <div class="d-flex justify-content-between align-items-center mb-1">
              <label for="trigger-entity" class="form-label mb-0">Binary Sensor</label>
              <button class="btn btn-sm btn-outline-secondary" onclick="loadBinarySensors()" style="font-size:10px;padding:3px 8px">
                  <i class="bi bi-arrow-clockwise"></i> Refresh
              </button>
          </div>
          <select class="form-select mb-3" id="trigger-entity"
              data-current-value="{{ settings.trigger_entity or '' }}">
              <option value="">— Select a sensor —</option>
          </select>
          <button class="btn btn-outline-secondary btn-sm me-2" onclick="saveTriggerEntity()">Save</button>
          <button class="btn btn-outline-primary btn-sm" onclick="copyAutomationYaml()">
              <i class="bi bi-clipboard"></i> Copy automation YAML
          </button>
      </div>
  </div>
  ```

---

## Task 7: Settings JS — new functions

**Files:**
- Modify: `doorbell-addon/web/static/js/settings.js`

**Background:** Add to the `API` object, call `loadNotifyServices()` and `loadBinarySensors()` from `initializeSettings()`, and implement the new save/YAML functions. The AI description warning is checked in `initializeSettings` and on toggle change. Use the existing `loadDropdownOptions` pattern for binary sensors.

- [ ] **Step 1: Add new API routes to the `API` object** (at the top of `settings.js`):

  ```javascript
  const API = {
      settings: 'api/settings',
      cameras: 'api/cameras',
      weatherEntities: 'api/weather-entities',
      cameraTest: 'api/camera/test',
      notifyServices: 'api/settings/notify-services',
      binarySensors: 'api/settings/binary-sensors',
  };
  ```

- [ ] **Step 2: Call new loaders from `initializeSettings`**

  Inside `initializeSettings()`, after the existing `loadDropdownOptions` calls, add:

  ```javascript
      loadNotifyServices();
      loadDropdownOptions(
          'trigger-entity',
          API.binarySensors,
          data => data.entities || [],
          e => ({ value: e.entity_id, label: e.friendly_name }),
          'No binary sensors found',
          'Error loading sensors'
      );
      checkAiPublicPathWarning();
  ```

  **Note on pre-selection:** `loadDropdownOptions` already restores the pre-saved value by reading the `data-current-value` attribute on the `<select>` element (set by Jinja2 from `settings.trigger_entity`). No additional code needed.

  Also wire up the LLM enabled toggle:

  ```javascript
      const llmToggle = document.getElementById('llmvision-enabled');
      if (llmToggle) llmToggle.addEventListener('change', checkAiPublicPathWarning);
  ```

- [ ] **Step 3: Add `loadNotifyServices` function**

  ```javascript
  async function loadNotifyServices() {
      const container = document.getElementById('notify-services-list');
      if (!container) return;
      container.innerHTML = '<span class="text-muted small">Loading…</span>';
      try {
          const resp = await fetch(API.notifyServices);
          const data = await resp.json();
          const services = data.services || [];
          if (services.length === 0) {
              container.innerHTML = '<span class="text-muted small">No notify services found.</span>';
              return;
          }
          const currentSelected = (window._currentNotifyServices || []);
          container.innerHTML = services.map(s => {
              const suffix = s.name.replace('notify.', '');
              const badge = s.classification === 'image'
                  ? '<span class="badge bg-primary ms-1" title="Image capable">📱 Mobile</span>'
                  : s.classification === 'audio'
                  ? '<span class="badge bg-secondary ms-1" title="Audio only">🔊 Audio</span>'
                  : '<span class="badge bg-info ms-1" title="Full payload">📡 Other</span>';
              const checked = currentSelected.includes(s.name) ? 'checked' : '';
              return `<div class="form-check">
                  <input class="form-check-input notify-service-check" type="checkbox"
                      value="${s.name}" id="ns-${suffix}" ${checked}>
                  <label class="form-check-label" for="ns-${suffix}">
                      ${suffix} ${badge}
                  </label>
              </div>`;
          }).join('');
      } catch (e) {
          container.innerHTML = '<span class="text-danger small">Error loading services.</span>';
      }
  }
  ```

- [ ] **Step 4: Add `checkAiPublicPathWarning` function**

  ```javascript
  function checkAiPublicPathWarning() {
      const enabled = document.getElementById('llmvision-enabled');
      const pathInput = document.getElementById('public-image-path');
      const warning = document.getElementById('ai-public-path-warning');
      if (!enabled || !warning) return;
      const needsWarning = enabled.checked && !(pathInput && pathInput.value.trim());
      warning.style.display = needsWarning ? '' : 'none';
  }
  ```

- [ ] **Step 5: Add `saveAiDescription` function**

  ```javascript
  async function saveAiDescription() {
      try {
          const payload = {
              llmvision_enabled: document.getElementById('llmvision-enabled').checked,
              llmvision_provider: document.getElementById('llmvision-provider').value.trim() || null,
              llmvision_model: document.getElementById('llmvision-model').value.trim(),
              llmvision_prompt: document.getElementById('llmvision-prompt').value,
              llmvision_max_tokens: parseInt(document.getElementById('llmvision-max-tokens').value),
              default_message: document.getElementById('default-message').value.trim(),
          };
          const resp = await fetch(API.settings, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(payload),
          });
          if (resp.ok) {
              alert('AI description settings saved!');
              checkAiPublicPathWarning();
          } else {
              const err = await resp.json();
              alert('Error: ' + (err.detail || 'Unknown error'));
          }
      } catch (e) {
          alert('Error saving AI settings: ' + e.message);
      }
  }
  ```

- [ ] **Step 6: Add `saveNotifications` function**

  ```javascript
  async function saveNotifications() {
      try {
          const checks = document.querySelectorAll('.notify-service-check:checked');
          const selectedServices = Array.from(checks).map(c => c.value);
          window._currentNotifyServices = selectedServices;
          const webhookUrl = document.getElementById('webhook-url').value.trim();
          const resp = await fetch(API.settings, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                  ha_notify_services: selectedServices,
                  notification_webhook: webhookUrl || null,
              }),
          });
          if (resp.ok) {
              alert('Notification settings saved!');
          } else {
              const err = await resp.json();
              alert('Error: ' + (err.detail || 'Unknown error'));
          }
      } catch (e) {
          alert('Error saving notification settings: ' + e.message);
      }
  }
  ```

- [ ] **Step 7: Add `savePublicImagePath` function**

  ```javascript
  async function savePublicImagePath() {
      try {
          const path = document.getElementById('public-image-path').value.trim();
          const resp = await fetch(API.settings, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ public_image_path: path || null }),
          });
          if (resp.ok) {
              alert('Public image path saved!');
              checkAiPublicPathWarning();
          } else {
              const err = await resp.json();
              alert('Error: ' + (err.detail || 'Unknown error'));
          }
      } catch (e) {
          alert('Error saving public image path: ' + e.message);
      }
  }
  ```

- [ ] **Step 8: Add `saveTriggerEntity` and `copyAutomationYaml` functions**

  ```javascript
  async function saveTriggerEntity() {
      try {
          const entity = document.getElementById('trigger-entity').value;
          const resp = await fetch(API.settings, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ trigger_entity: entity || null }),
          });
          if (resp.ok) { alert('Trigger entity saved!'); }
          else { const err = await resp.json(); alert('Error: ' + (err.detail || 'Unknown')); }
      } catch (e) { alert('Error: ' + e.message); }
  }

  function copyAutomationYaml() {
      const entity = document.getElementById('trigger-entity').value;
      if (!entity) { alert('Select a binary sensor first.'); return; }
      const yaml = `# Add to configuration.yaml:
  rest_command:
    doorbell_ring:
      url: "http://localhost:8099/api/doorbell/ring"
      method: POST

  # Automation:
  alias: Doorbell ring
  triggers:
    - trigger: state
      entity_id: ${entity}
      from: "off"
      to: "on"
  actions:
    - action: rest_command.doorbell_ring`;
      navigator.clipboard.writeText(yaml)
          .then(() => alert('Automation YAML copied to clipboard!'))
          .catch(() => { alert('Copy failed. YAML:\n\n' + yaml); });
  }
  ```

- [ ] **Step 9: Pre-select saved notify services on page load**

  In `initializeSettings`, after `loadCurrentSettings().then(...)`, read the current `ha_notify_services` from settings to pre-check the boxes after `loadNotifyServices` runs:

  ```javascript
      loadCurrentSettings().then(data => {
          // ... existing dropdown loads ...
          window._currentNotifyServices = data.ha_notify_services || [];
          loadNotifyServices();
          // ... rest ...
      });
  ```

  This requires `loadCurrentSettings` to return the full settings object. Verify the existing `loadCurrentSettings` function returns the settings data (it should if it returns `response.json()`). If it does not return the data, update it to `return response.json()`.

---

## Task 8: `config.yaml` — `config:rw`

**Files:**
- Modify: `doorbell-addon/config.yaml`

**Background:** The addon needs write access to `/config` (specifically `/config/www`) to write public image copies that HA serves at `/local/<filename>`. This requires changing the `config` map entry from read-only to read-write.

- [ ] **Step 1: Change `config:ro` to `config:rw`**

  In `doorbell-addon/config.yaml`, in the `map:` section, change:

  ```yaml
    - "config:ro"
  ```

  to:

  ```yaml
    - "config:rw"
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add doorbell-addon/config.yaml
  git commit -m "feat: config:rw mapping for public image write access"
  ```

---

## Task 9: Version bump + release

**Files:**
- Modify: `doorbell-addon/config.yaml`
- Modify: `doorbell-addon/build.yaml`
- Modify: `doorbell-addon/requirements.txt`
- Modify: `doorbell-addon/src/config.py`

**Background:** Version must be consistent across all four files. Current version is `1.0.141`; bump to `1.0.142`.

- [ ] **Step 1: Run full test suite to confirm clean baseline**

  ```bash
  cd doorbell-addon && python -m pytest tests/ -v
  ```

  Expected: All tests PASS

- [ ] **Step 2: Run linter**

  ```bash
  cd doorbell-addon && flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics
  ```

  Expected: 0 errors

- [ ] **Step 3: Bump version in all four files**

  - `doorbell-addon/config.yaml`: `version: "1.0.141"` → `version: "1.0.142"`
  - `doorbell-addon/build.yaml`: both `org.opencontainers.image.version: "1.0.141"` and `DOORBELL_VERSION: "1.0.141"` → `1.0.142`
  - `doorbell-addon/requirements.txt`: `# Version: 1.0.141` → `# Version: 1.0.142`
  - `doorbell-addon/src/config.py`: `app_version: ClassVar[str] = "1.0.141"` → `"1.0.142"`

- [ ] **Step 4: Commit version bump**

  ```bash
  git add doorbell-addon/config.yaml doorbell-addon/build.yaml doorbell-addon/requirements.txt doorbell-addon/src/config.py
  git commit -m "Release v1.0.142 - Automation integration (LLM + HA push notifications)"
  ```

- [ ] **Step 5: Tag and push**

  ```bash
  git tag v1.0.142
  git push origin main --tags
  ```

---

## Verification Checklist

After all tasks complete, smoke-test the following:

1. **No settings configured** — ring a doorbell, confirm event saved with `default_message`, no errors in logs
2. **AI description** — set `public_image_path=/config/www`, enable LLM, configure a valid `llmvision_provider`, ring doorbell — confirm `ai_message` is LLM-generated in event
3. **LLM degradation** — set `llmvision_enabled=true` but no `public_image_path` — confirm ring succeeds with `default_message`
4. **HA Push notifications** — select `notify.mobile_app_*` service in Settings, ring doorbell — confirm mobile notification received with image
5. **Audio service** — add a `tts_*` service, ring — confirm notification sent without `data.image`
6. **Public image copy** — after ring, confirm `doorbell_<timestamp>.jpg` exists in `/config/www`
7. **Trigger Helper** — select a binary sensor, click "Copy automation YAML" — confirm YAML in clipboard includes `rest_command` definition and correct `entity_id`
8. **Backward compat** — post to ring endpoint with `ai_message` form field — confirm LLM is skipped, response has all fields
