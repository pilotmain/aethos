"""Telegram voice notes — transcription stub (Phase 53; feature-flagged)."""

from __future__ import annotations

from app.core.config import get_settings


def voice_feature_enabled() -> bool:
    s = get_settings()
    return bool(getattr(s, "nexa_voice_enabled", False))


async def transcribe_telegram_voice_stub(_file_bytes: bytes) -> str | None:
    """Return None until real Whisper/local pipeline is wired."""
    if not voice_feature_enabled():
        return None
    return None


__all__ = ["transcribe_telegram_voice_stub", "voice_feature_enabled"]
