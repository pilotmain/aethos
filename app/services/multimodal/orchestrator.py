"""Phase 18a/b — multimodal orchestration (vision wired in 18b)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.llm.base import Message
from app.services.llm.content_parts import image_base64_block, text_block
from app.services.llm.vision_llm import normalize_messages_with_remote_images, vision_complete_chat

from .models import MultimodalPhase18APlaceholder

logger = logging.getLogger(__name__)


def max_image_bytes_cap() -> int:
    s = get_settings()
    mb = max(int(getattr(s, "nexa_multimodal_max_image_mb", 10) or 10), 1)
    return min(mb, 512) * 1024 * 1024  # hard ceiling 512 MB for config mistakes


def multimodal_globally_enabled() -> bool:
    return bool(get_settings().nexa_multimodal_enabled)


def vision_enabled() -> bool:
    s = get_settings()
    return bool(s.nexa_multimodal_enabled and s.nexa_multimodal_vision_enabled)


def audio_input_enabled() -> bool:
    s = get_settings()
    if not s.nexa_multimodal_enabled:
        return False
    if bool(getattr(s, "nexa_multimodal_audio_enabled", False)):
        return True
    return bool(s.nexa_audio_input_enabled)


def audio_output_enabled() -> bool:
    s = get_settings()
    if not s.nexa_multimodal_enabled:
        return False
    if bool(getattr(s, "nexa_multimodal_audio_enabled", False)):
        return True
    return bool(s.nexa_audio_output_enabled)


def image_gen_enabled() -> bool:
    s = get_settings()
    if not s.nexa_multimodal_enabled:
        return False
    if bool(getattr(s, "nexa_multimodal_image_enabled", False)):
        return True
    return bool(s.nexa_image_gen_enabled)


def _allowed_image_mime(m: str) -> bool:
    x = (m or "").split(";")[0].strip().lower()
    if x == "image/jpg":
        x = "image/jpeg"
    return x in ("image/png", "image/jpeg", "image/webp", "image/gif")


def _maybe_strip_metadata(mime: str, image_bytes: bytes) -> tuple[str, bytes]:
    s = get_settings()
    if not s.nexa_multimodal_strip_image_metadata:
        return mime, image_bytes
    m = (mime or "").split(";")[0].strip().lower()
    if m not in ("image/jpeg", "image/png", "image/jpg"):
        return mime, image_bytes
    try:
        import io

        from PIL import Image  # type: ignore[import-untyped]

        img = Image.open(io.BytesIO(image_bytes))
        buf = io.BytesIO()
        if m in ("image/jpeg", "image/jpg") or img.format == "JPEG":
            rgb = img.convert("RGB")
            rgb.save(buf, format="JPEG", quality=90)
            return "image/jpeg", buf.getvalue()
        img.save(buf, format="PNG")
        return "image/png", buf.getvalue()
    except Exception:  # noqa: BLE001
        return mime, image_bytes


def analyze_image_bytes(
    *,
    image_bytes: bytes,
    mime: str,
    prompt: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    cap = max_image_bytes_cap()
    if len(image_bytes) > cap:
        return {
            "ok": False,
            "code": "IMAGE_TOO_LARGE",
            "error": f"image exceeds cap ({cap} bytes)",
        }
    m0 = (mime or "image/png").split(";")[0].strip()
    m0, image_bytes = _maybe_strip_metadata(m0, image_bytes)
    if not _allowed_image_mime(m0):
        return {"ok": False, "code": "UNSUPPORTED_MIME", "error": m0}
    user_text = (prompt or "").strip() or "Describe this image succinctly for the user."
    blocks: list[dict[str, Any]] = [text_block(user_text), image_base64_block(m0, image_bytes)]
    messages = [Message(role="user", content=blocks)]
    try:
        text, meta = vision_complete_chat(messages)
    except Exception as exc:  # noqa: BLE001
        logger.warning("vision_complete_chat failed: %s", exc)
        return {"ok": False, "code": "VISION_FAILED", "error": str(exc)[:2000]}
    return {
        "ok": True,
        "text": text,
        "model": meta.get("model"),
        "provider": meta.get("provider"),
        "usage": {},
        "session_id": session_id,
    }


def analyze_image_url(
    *,
    image_url: str,
    prompt: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    u = (image_url or "").strip()
    if not u:
        return {"ok": False, "code": "MISSING_URL", "error": "image_url is required"}
    if u.startswith("data:"):
        from app.services.llm.content_parts import parse_data_url

        parsed = parse_data_url(u)
        if not parsed:
            return {"ok": False, "code": "INVALID_DATA_URL", "error": "could not parse data URL"}
        mime, raw = parsed
        if len(raw) > max_image_bytes_cap():
            return {"ok": False, "code": "IMAGE_TOO_LARGE", "error": "image exceeds cap"}
        return analyze_image_bytes(image_bytes=raw, mime=mime, prompt=prompt, session_id=session_id)
    if u.startswith("http://") or u.startswith("https://"):
        try:
            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                r = client.get(u)
                r.raise_for_status()
                body = r.content
                ct = (r.headers.get("content-type") or "image/jpeg").split(";")[0].strip()
            if len(body) > max_image_bytes_cap():
                return {"ok": False, "code": "IMAGE_TOO_LARGE", "error": "image exceeds cap"}
            if not ct.startswith("image/"):
                return {"ok": False, "code": "NOT_AN_IMAGE", "error": ct}
            return analyze_image_bytes(image_bytes=body, mime=ct, prompt=prompt, session_id=session_id)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "code": "FETCH_FAILED", "error": str(exc)[:2000]}
    return {"ok": False, "code": "UNSUPPORTED_URL", "error": "use http(s) or data: URL"}


def analyze_image_message_blocks(
    blocks: list[dict[str, Any]],
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Run vision on a fully built OpenAI-style user content (for JSON clients)."""
    try:
        msgs0 = [Message(role="user", content=blocks)]
        msgs = normalize_messages_with_remote_images(msgs0, max_bytes=max_image_bytes_cap())
        text, meta = vision_complete_chat(msgs)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "code": "VISION_FAILED", "error": str(exc)[:2000]}
    return {
        "ok": True,
        "text": text,
        "model": meta.get("model"),
        "provider": meta.get("provider"),
        "usage": {},
        "session_id": session_id,
    }


async def analyze_image_stub(*, prompt: str | None = None, session_id: str | None = None) -> dict[str, Any]:
    """Deprecated placeholder — use :func:`analyze_image_bytes`."""
    _ = (prompt, session_id)
    raise MultimodalPhase18APlaceholder()


def transcribe_uploaded_audio_bytes(
    data: bytes,
    *,
    filename: str,
    mime: str | None,
) -> dict[str, Any]:
    """STT entry point for HTTP and channels — see :mod:`app.services.multimodal.stt`."""
    from app.services.multimodal import stt as stt_mod

    return stt_mod.transcribe_audio_bytes(data, filename=filename, mime=mime)


def synthesize_spoken_audio(text: str, *, voice: str | None = None) -> dict[str, Any]:
    """TTS entry point — see :mod:`app.services.multimodal.tts`."""
    from app.services.multimodal import tts as tts_mod

    return tts_mod.synthesize_speech_bytes(text, voice=voice)


async def transcribe_audio_stub(*, mime: str | None = None) -> dict[str, Any]:
    """Deprecated — use :func:`transcribe_uploaded_audio_bytes`."""
    _ = mime
    raise MultimodalPhase18APlaceholder()


async def synthesize_speech_stub(*, text: str, voice: str | None = None) -> dict[str, Any]:
    """Deprecated — use :func:`synthesize_spoken_audio`."""
    _ = (text, voice)
    raise MultimodalPhase18APlaceholder()


def generate_images_from_prompt(
    prompt: str,
    *,
    size: str | None = None,
    quality: str | None = None,
    n: int = 1,
) -> dict[str, Any]:
    """Image generation for HTTP and channels — see :mod:`app.services.multimodal.image_generation`."""
    from app.services.multimodal import image_generation as ig_mod

    return ig_mod.generate_images(prompt, size=size, quality=quality, n=n)


async def generate_image_stub(
    *, prompt: str, size: str | None = None, n: int = 1
) -> dict[str, Any]:
    """Deprecated — use :func:`generate_images_from_prompt`."""
    _ = (prompt, size, n)
    raise MultimodalPhase18APlaceholder()
