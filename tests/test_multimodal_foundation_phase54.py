from __future__ import annotations

from app.services.media.multimodal import route_multimodal_image


def test_multimodal_strict_without_local(monkeypatch) -> None:
    monkeypatch.setenv("NEXA_STRICT_PRIVACY_MODE", "true")
    monkeypatch.setenv("NEXA_LOCAL_FIRST", "false")
    monkeypatch.setenv("NEXA_OLLAMA_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        out = route_multimodal_image(metadata={"w": 10}, user_id="u")
        assert out["ok"] is False
    finally:
        get_settings.cache_clear()
