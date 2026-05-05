"""Phase 18a — multimodal flags, skeleton routes, auth."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_multimodal_status_ok(api_client) -> None:
    client, uid = api_client
    r = client.get("/api/v1/multimodal/status", headers={"X-User-Id": uid})
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("phase") == "18d"
    assert "vision" in body and "audio" in body and "limits" in body


def test_multimodal_status_requires_auth() -> None:
    from app.core.security import get_valid_web_user_id

    app.dependency_overrides.pop(get_valid_web_user_id, None)
    try:
        with TestClient(app) as c:
            r = c.get("/api/v1/multimodal/status")
            assert r.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_vision_analyze_503_when_multimodal_off(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_MULTIMODAL_ENABLED", "false")
    get_settings.cache_clear()
    client, uid = api_client
    r = client.post(
        "/api/v1/multimodal/vision/analyze",
        headers={"X-User-Id": uid},
        files={"image": ("x.png", b"\x89PNG\r\n", "image/png")},
    )
    assert r.status_code == 503


def test_vision_analyze_200_when_flags_on(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_MULTIMODAL_ENABLED", "true")
    monkeypatch.setenv("NEXA_MULTIMODAL_VISION_ENABLED", "true")
    get_settings.cache_clear()

    def _fake_vision(msgs):  # noqa: ANN001
        return ("stub description", {"provider": "openai", "model": "gpt-4o"})

    monkeypatch.setattr(
        "app.services.multimodal.orchestrator.vision_complete_chat",
        _fake_vision,
    )
    client, uid = api_client
    r = client.post(
        "/api/v1/multimodal/vision/analyze",
        headers={"X-User-Id": uid},
        files={"image": ("x.png", b"\x89PNG\r\n\x00\x00\x00\x00\x00\x00\x00", "image/png")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("text") == "stub description"


def test_audio_transcribe_503_when_inputs_disabled(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_MULTIMODAL_ENABLED", "true")
    monkeypatch.setenv("NEXA_AUDIO_INPUT_ENABLED", "false")
    monkeypatch.setenv("NEXA_MULTIMODAL_AUDIO_ENABLED", "false")
    get_settings.cache_clear()
    client, uid = api_client
    r = client.post(
        "/api/v1/multimodal/audio/transcribe",
        headers={"X-User-Id": uid},
        files={"audio": ("x.ogg", b"fake", "audio/ogg")},
    )
    assert r.status_code == 503


def test_audio_transcribe_200_when_master_audio_flag(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_MULTIMODAL_ENABLED", "true")
    monkeypatch.setenv("NEXA_MULTIMODAL_AUDIO_ENABLED", "true")
    get_settings.cache_clear()

    def _fake_stt(
        data: bytes,
        *,
        filename: str,
        mime: str | None,
    ) -> dict:
        _ = (data, filename, mime)
        return {"ok": True, "text": "hello from stub", "language": "en", "provider": "openai"}

    monkeypatch.setattr(
        "app.api.routes.multimodal.transcribe_uploaded_audio_bytes",
        _fake_stt,
    )
    client, uid = api_client
    r = client.post(
        "/api/v1/multimodal/audio/transcribe",
        headers={"X-User-Id": uid},
        files={"audio": ("x.ogg", b"\x00oggs", "audio/ogg")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("text") == "hello from stub"
    assert body.get("provider") == "openai"


def test_audio_speak_503_when_output_disabled(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_MULTIMODAL_ENABLED", "true")
    monkeypatch.setenv("NEXA_AUDIO_OUTPUT_ENABLED", "false")
    monkeypatch.setenv("NEXA_MULTIMODAL_AUDIO_ENABLED", "false")
    get_settings.cache_clear()
    client, uid = api_client
    r = client.post(
        "/api/v1/multimodal/audio/speak",
        headers={"X-User-Id": uid},
        json={"text": "Hello"},
    )
    assert r.status_code == 503


def test_audio_speak_200_when_master_audio_flag(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_MULTIMODAL_ENABLED", "true")
    monkeypatch.setenv("NEXA_MULTIMODAL_AUDIO_ENABLED", "true")
    get_settings.cache_clear()

    def _fake_tts(text: str, *, voice: str | None = None) -> dict:
        _ = voice
        return {
            "ok": True,
            "audio_bytes": b"\xff\xfb" + text.encode(),
            "mime_type": "audio/mpeg",
            "provider": "openai",
        }

    monkeypatch.setattr(
        "app.api.routes.multimodal.synthesize_spoken_audio",
        _fake_tts,
    )
    client, uid = api_client
    r = client.post(
        "/api/v1/multimodal/audio/speak",
        headers={"X-User-Id": uid},
        json={"text": "Hi there"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("mime_type") == "audio/mpeg"
    assert body.get("provider") == "openai"
    assert "audio_base64" in body and len(body["audio_base64"]) > 4


def test_image_generate_503_when_gen_disabled(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_MULTIMODAL_ENABLED", "true")
    monkeypatch.setenv("NEXA_IMAGE_GEN_ENABLED", "false")
    monkeypatch.setenv("NEXA_MULTIMODAL_IMAGE_ENABLED", "false")
    get_settings.cache_clear()
    client, uid = api_client
    r = client.post(
        "/api/v1/multimodal/image/generate",
        headers={"X-User-Id": uid},
        json={"prompt": "a red balloon"},
    )
    assert r.status_code == 503


def test_image_generate_200_when_master_image_flag(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_MULTIMODAL_ENABLED", "true")
    monkeypatch.setenv("NEXA_MULTIMODAL_IMAGE_ENABLED", "true")
    get_settings.cache_clear()

    def _fake_gen(
        prompt: str,
        *,
        size: str | None = None,
        quality: str | None = None,
        n: int = 1,
    ) -> dict:
        _ = (size, quality, n)
        return {
            "ok": True,
            "provider": "openai",
            "model": "dall-e-3",
            "images": [{"url": "https://example.com/img.png"}],
        }

    monkeypatch.setattr(
        "app.api.routes.multimodal.generate_images_from_prompt",
        _fake_gen,
    )
    client, uid = api_client
    r = client.post(
        "/api/v1/multimodal/image/generate",
        headers={"X-User-Id": uid},
        json={"prompt": "a red balloon", "quality": "standard", "n": 1},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("provider") == "openai"
    assert isinstance(body.get("images"), list) and len(body["images"]) == 1
