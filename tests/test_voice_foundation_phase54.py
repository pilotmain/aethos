from __future__ import annotations

from app.services.media.voice import transcribe_voice_note_allowed


def test_voice_strict_blocks_external_provider(monkeypatch) -> None:
    monkeypatch.setenv("NEXA_STRICT_PRIVACY_MODE", "true")
    monkeypatch.setenv("NEXA_VOICE_TRANSCRIBE_PROVIDER", "openai")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        ok, reason = transcribe_voice_note_allowed(user_id="u")
        assert ok is False
        assert "strict" in reason.lower() or "privacy" in reason.lower()
    finally:
        get_settings.cache_clear()
