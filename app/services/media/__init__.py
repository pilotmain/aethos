"""Media pipeline stubs — STT/TTS/images/docs (Phase 22 extension points)."""

from __future__ import annotations

from typing import Any


class MediaPipeline:
    """Whisper/TTS/image/document helpers ship as optional deps."""

    def transcribe_audio_stub(self, _audio_bytes: bytes, *, user_id: str) -> dict[str, Any]:
        _ = user_id
        return {"ok": False, "error": "whisper_not_configured"}

    def synthesize_speech_stub(self, _text: str, *, user_id: str) -> dict[str, Any]:
        _ = user_id
        return {"ok": False, "error": "tts_not_configured"}


__all__ = ["MediaPipeline"]
