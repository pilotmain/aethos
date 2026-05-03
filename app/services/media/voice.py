"""Telegram voice notes — transcription policy + stub pipeline."""

from __future__ import annotations

import logging

from app.core.config import get_settings

_log = logging.getLogger(__name__)


def voice_feature_enabled() -> bool:
    s = get_settings()
    return bool(getattr(s, "nexa_voice_enabled", False))


def transcribe_voice_note_allowed(*, user_id: str | None) -> tuple[bool, str]:
    """
    Returns ``(allowed, reason)``. Strict privacy blocks external transcription providers.
    Does not log audio bytes.
    """
    _ = user_id
    s = get_settings()
    strict = bool(getattr(s, "nexa_strict_privacy_mode", False))
    prov = (getattr(s, "nexa_voice_transcribe_provider", None) or "local").strip().lower()
    external = prov not in ("local", "none", "offline", "")
    if strict and external:
        return False, "voice_external_disabled_strict_privacy"
    return True, "ok"


async def transcribe_telegram_voice_stub(file_bytes: bytes) -> str | None:
    """Return None until Whisper/local pipeline is wired."""
    _ = file_bytes
    if not voice_feature_enabled():
        return None
    ok, reason = transcribe_voice_note_allowed(user_id=None)
    if not ok:
        _log.info("voice_transcribe_blocked reason=%s", reason)
        return None
    return None


__all__ = ["transcribe_telegram_voice_stub", "transcribe_voice_note_allowed", "voice_feature_enabled"]
