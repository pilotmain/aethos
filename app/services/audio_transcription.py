# Future: Telegram voice and web microphone — transcribe then run normal Nexa message pipeline.
# Env (planned): NEXA_AUDIO_INPUT_ENABLED, NEXA_TRANSCRIPTION_PROVIDER, NEXA_TRANSCRIPTION_API_KEY
# Not implemented in the document-generation milestone.

from __future__ import annotations

from pathlib import Path


def transcribe_audio_file(file_path: Path, user_id: str) -> str:  # pragma: no cover
    """
    STUB: will call provider (e.g. OpenAI Whisper) and return text.
    Safety: user-owned file only; delete temp audio after use unless user opts in.
    """
    raise NotImplementedError("Audio transcription is not enabled yet.")


def transcribe_telegram_voice(file_id: str, user_id: str) -> str:  # pragma: no cover
    """STUB: download Telegram file → temp path → transcribe_audio_file."""
    raise NotImplementedError("Audio transcription is not enabled yet.")
