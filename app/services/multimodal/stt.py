# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Speech-to-text — OpenAI Whisper API primary; optional local fallback (Phase 18c)."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.services.llm_key_resolution import get_merged_api_keys
from app.services.network_policy.policy import assert_provider_egress_allowed

logger = logging.getLogger(__name__)

_ALLOWED_AUDIO_PREFIXES = (
    "audio/",
    "video/webm",
    "application/ogg",
)


def audio_mime_allowed(mime: str) -> bool:
    m = (mime or "").split(";")[0].strip().lower()
    return any(m.startswith(p) or m == p.rstrip("/") for p in _ALLOWED_AUDIO_PREFIXES)


def transcribe_audio_bytes(
    data: bytes,
    *,
    filename: str,
    mime: str | None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """
    Transcribe voice/audio bytes. Returns ``{ok, text, language?, provider}``.
    """
    s = settings or get_settings()
    prov = (s.nexa_audio_transcription_provider or "openai").strip().lower()
    max_b = max_audio_bytes_cap(s)
    if len(data) > max_b:
        return {"ok": False, "code": "AUDIO_TOO_LARGE", "error": f"max {max_b} bytes"}

    if prov == "openai":
        out = _transcribe_openai_whisper(data, filename=filename, mime=mime, settings=s)
        if out.get("ok"):
            return out
        # Fallback to local when primary fails and bytes still usable
        fb = _transcribe_local_fallback(data, filename=filename)
        if fb.get("ok"):
            fb["provider"] = "local_fallback"
            return fb
        return out

    if prov in ("local", "offline"):
        return _transcribe_local_fallback(data, filename=filename)

    return {"ok": False, "code": "UNSUPPORTED_STT_PROVIDER", "error": prov}


def max_audio_bytes_cap(s: Settings | None = None) -> int:
    st = s or get_settings()
    mb = max(int(getattr(st, "nexa_multimodal_max_audio_mb", 25) or 25), 1)
    return min(mb, 100) * 1024 * 1024


def _resolve_openai_key(st: Settings) -> str | None:
    m = get_merged_api_keys()
    return (m.openai_api_key or st.openai_api_key or st.nexa_llm_api_key or "").strip() or None


def _transcribe_openai_whisper(
    data: bytes,
    *,
    filename: str,
    mime: str | None,
    settings: Settings,
) -> dict[str, Any]:
    block = assert_provider_egress_allowed("openai", None)
    if block:
        return {"ok": False, "code": "EGRESS_BLOCKED", "error": block}
    key = _resolve_openai_key(settings)
    if not key:
        return {"ok": False, "code": "MISSING_OPENAI_KEY", "error": "Configure OpenAI API key for Whisper"}

    fn = (filename or "audio.bin").strip() or "audio.bin"
    ct = (mime or "application/octet-stream").split(";")[0].strip()
    files = {"file": (fn, data, ct)}
    form = {"model": "whisper-1"}
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        with httpx.Client(timeout=180.0) as client:
            r = client.post(url, headers=headers, files=files, data=form)
            r.raise_for_status()
            body = r.json()
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = (exc.response.text or "")[:500]
        except Exception:  # noqa: BLE001
            detail = str(exc)
        logger.warning("openai whisper http error: %s", detail)
        return {"ok": False, "code": "WHISPER_HTTP_ERROR", "error": detail}
    except Exception as exc:  # noqa: BLE001
        logger.warning("openai whisper failed: %s", exc)
        return {"ok": False, "code": "WHISPER_FAILED", "error": str(exc)[:1000]}

    text = str(body.get("text") or "").strip()
    lang = body.get("language") if isinstance(body.get("language"), str) else None
    return {"ok": True, "text": text, "language": lang, "provider": "openai"}


def _transcribe_local_fallback(data: bytes, *, filename: str) -> dict[str, Any]:
    suffix = Path(filename or "audio.bin").suffix or ".ogg"
    try:
        from faster_whisper import WhisperModel  # type: ignore[import-untyped]
    except Exception:
        WhisperModel = None  # type: ignore[misc,assignment]

    if WhisperModel is not None:
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
                tmp.write(data)
                tmp.flush()
                model = WhisperModel("tiny", device="cpu", compute_type="int8")
                segments, _info = model.transcribe(tmp.name)
                text = "".join(seg.text for seg in segments).strip()
                return {"ok": True, "text": text, "language": None, "provider": "faster_whisper"}
        except Exception as exc:  # noqa: BLE001
            logger.warning("faster_whisper failed: %s", exc)

    # CLI `whisper` (openai-whisper package)
    if shutil.which("whisper"):
        out_dir = tempfile.mkdtemp(prefix="nexa_whisper_")
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, prefix="nexa_voice_") as tmp:
            tmp.write(data)
            path = Path(tmp.name)
        try:
            subprocess.run(
                ["whisper", str(path), "--model", "tiny", "--output_dir", out_dir, "--output_format", "txt"],
                check=True,
                capture_output=True,
                text=True,
                timeout=600,
            )
            txt_files = list(Path(out_dir).glob("*.txt"))
            if txt_files:
                text = txt_files[0].read_text(encoding="utf-8", errors="replace").strip()
                return {"ok": True, "text": text, "language": None, "provider": "whisper_cli"}
        except Exception as exc:  # noqa: BLE001
            logger.warning("whisper cli failed: %s", exc)
        finally:
            path.unlink(missing_ok=True)
            shutil.rmtree(out_dir, ignore_errors=True)

    return {
        "ok": False,
        "code": "LOCAL_STT_UNAVAILABLE",
        "error": "Install faster-whisper (pip install faster-whisper) or OpenAI Whisper CLI, or use OpenAI API.",
    }
