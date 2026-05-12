# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Telegram voice message hooks — feature-flagged (Phase 54).

Wire handlers to call :func:`app.services.media.voice.transcribe_telegram_voice_stub`
when ``NEXA_VOICE_ENABLED`` is true.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.media.voice import transcribe_voice_note_allowed, voice_feature_enabled

if TYPE_CHECKING:
    pass


def voice_handling_enabled() -> bool:
    return voice_feature_enabled()


def describe_voice_policy() -> str:
    ok, reason = transcribe_voice_note_allowed(user_id=None)
    if not ok:
        return f"Voice transcription unavailable ({reason})."
    return "Voice pipeline stub — enable NEXA_VOICE_ENABLED when ready."


__all__ = ["describe_voice_policy", "voice_handling_enabled"]
