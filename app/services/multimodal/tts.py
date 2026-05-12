# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Text-to-speech — OpenAI Speech API or ElevenLabs (Phase 18c)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.services.llm_key_resolution import get_merged_api_keys
from app.services.network_policy.policy import assert_provider_egress_allowed

logger = logging.getLogger(__name__)


def synthesize_speech_bytes(
    text: str,
    *,
    voice: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Return ``{ok, audio_bytes, mime_type, provider}``."""
    s = settings or get_settings()
    prov = (s.nexa_audio_output_provider or "openai").strip().lower()
    if prov == "elevenlabs":
        return _tts_elevenlabs(text, voice=voice, settings=s)
    return _tts_openai(text, voice=voice, settings=s)


def _resolve_openai_key(st: Settings) -> str | None:
    m = get_merged_api_keys()
    return (m.openai_api_key or st.openai_api_key or st.nexa_llm_api_key or "").strip() or None


def _tts_openai(text: str, *, voice: str | None, settings: Settings) -> dict[str, Any]:
    block = assert_provider_egress_allowed("openai", None)
    if block:
        return {"ok": False, "code": "EGRESS_BLOCKED", "error": block}
    key = _resolve_openai_key(settings)
    if not key:
        return {"ok": False, "code": "MISSING_OPENAI_KEY", "error": "Configure OpenAI API key for TTS"}

    model = (settings.nexa_openai_tts_model or "tts-1").strip()
    v = (voice or settings.nexa_openai_tts_voice or "alloy").strip()
    url = "https://api.openai.com/v1/audio/speech"
    payload = {"model": model, "voice": v, "input": text[:12000]}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=180.0) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            audio = r.content
    except Exception as exc:  # noqa: BLE001
        logger.warning("openai tts failed: %s", exc)
        return {"ok": False, "code": "TTS_FAILED", "error": str(exc)[:1000]}
    return {"ok": True, "audio_bytes": audio, "mime_type": "audio/mpeg", "provider": "openai"}


def _tts_elevenlabs(text: str, *, voice: str | None, settings: Settings) -> dict[str, Any]:
    block = assert_provider_egress_allowed("elevenlabs", None)
    if block:
        return {"ok": False, "code": "EGRESS_BLOCKED", "error": block}
    key = (settings.nexa_elevenlabs_api_key or "").strip()
    if not key:
        return {"ok": False, "code": "MISSING_ELEVENLABS_KEY", "error": "Set NEXA_ELEVENLABS_API_KEY"}

    vid = (voice or settings.nexa_elevenlabs_voice_id or "").strip()
    if not vid:
        return {"ok": False, "code": "MISSING_VOICE_ID", "error": "Set NEXA_ELEVENLABS_VOICE_ID"}

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"
    headers = {"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"}
    payload = {"text": text[:12000]}
    try:
        with httpx.Client(timeout=180.0) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            audio = r.content
    except Exception as exc:  # noqa: BLE001
        logger.warning("elevenlabs tts failed: %s", exc)
        return {"ok": False, "code": "TTS_FAILED", "error": str(exc)[:1000]}
    return {"ok": True, "audio_bytes": audio, "mime_type": "audio/mpeg", "provider": "elevenlabs"}
