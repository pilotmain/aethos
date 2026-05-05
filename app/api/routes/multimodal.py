"""Phase 18a/b — multimodal API (Mission Control auth; vision in 18b)."""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.security import get_valid_web_user_id
from app.services.multimodal.orchestrator import (
    analyze_image_bytes,
    analyze_image_message_blocks,
    analyze_image_url,
    audio_input_enabled,
    audio_output_enabled,
    image_gen_enabled,
    max_image_bytes_cap,
    multimodal_globally_enabled,
    vision_enabled,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/multimodal", tags=["multimodal"])


def _err(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "code": code, "error": message}


@router.get("/status")
def multimodal_status(
    _app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Non-secret feature flags for the current process (18a)."""
    s = get_settings()
    return {
        "ok": True,
        "phase": "18b",
        "nexa_multimodal_enabled": s.nexa_multimodal_enabled,
        "vision": {
            "enabled": vision_enabled(),
            "provider": (s.nexa_multimodal_vision_provider or "auto").strip(),
            "model": s.nexa_multimodal_vision_model,
        },
        "audio": {
            "input": audio_input_enabled(),
            "output": audio_output_enabled(),
            "transcription_provider": (s.nexa_audio_transcription_provider or "openai").strip(),
        },
        "image_gen": {
            "enabled": image_gen_enabled(),
            "provider": (s.nexa_image_gen_provider or "openai").strip(),
        },
        "limits": {
            "max_image_mb": int(s.nexa_multimodal_max_image_mb or 10),
            "max_audio_seconds": int(s.nexa_multimodal_max_audio_seconds or 300),
            "max_image_side_px": int(s.nexa_multimodal_max_image_side_px or 8192),
            "temp_ttl_seconds": int(s.nexa_multimodal_temp_ttl_seconds or 3600),
        },
    }


class VisionAnalyzeJson(BaseModel):
    """JSON body: image URL, raw base64, or OpenAI-style ``content`` blocks."""

    image_url: str | None = Field(default=None, max_length=8000)
    image_base64: str | None = Field(default=None)
    mime_type: str | None = Field(default="image/png", max_length=128)
    prompt: str | None = Field(default=None, max_length=8000)
    session_id: str | None = Field(default=None, max_length=128)
    content: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional OpenAI-style multimodal blocks (text + image_url parts)",
    )


@router.post("/vision/analyze")
async def vision_analyze(
    request: Request,
    _app_user_id: str = Depends(get_valid_web_user_id),
    image: UploadFile | None = File(None),
    prompt: str | None = Form(None),
    session_id: str | None = Form(None),
) -> dict[str, Any]:
    if not multimodal_globally_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_err("MULTIMODAL_DISABLED", "Set NEXA_MULTIMODAL_ENABLED=true after configuring providers"),
        )
    if not vision_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_err("VISION_DISABLED", "Enable NEXA_MULTIMODAL_VISION_ENABLED when the master flag is on"),
        )

    ct = (request.headers.get("content-type") or "").lower()
    cap = max_image_bytes_cap()

    if "application/json" in ct:
        try:
            raw_json = await request.json()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_err("INVALID_JSON", str(exc)[:500]),
            ) from exc
        payload = VisionAnalyzeJson.model_validate(raw_json)
        if payload.content:
            out = await asyncio.to_thread(
                analyze_image_message_blocks,
                payload.content,
                session_id=payload.session_id,
            )
        elif payload.image_url:
            out = await asyncio.to_thread(
                analyze_image_url,
                image_url=payload.image_url,
                prompt=payload.prompt,
                session_id=payload.session_id,
            )
        elif payload.image_base64:
            try:
                raw = base64.b64decode(payload.image_base64, validate=True)
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_err("INVALID_BASE64", str(exc)[:200]),
                ) from exc
            out = await asyncio.to_thread(
                analyze_image_bytes,
                image_bytes=raw,
                mime=payload.mime_type or "image/png",
                prompt=payload.prompt,
                session_id=payload.session_id,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_err("MISSING_IMAGE", "Provide content, image_url, or image_base64"),
            )
    else:
        if image is None or not getattr(image, "filename", None):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_err("MISSING_IMAGE", "multipart field `image` is required for non-JSON requests"),
            )
        try:
            raw = await image.read()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_err("READ_FAILED", str(exc)[:500]),
            ) from exc
        if len(raw) > cap:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=_err("IMAGE_TOO_LARGE", f"max {cap} bytes"),
            )
        mime = (image.content_type or "application/octet-stream").split(";")[0].strip()
        out = await asyncio.to_thread(
            analyze_image_bytes,
            image_bytes=raw,
            mime=mime,
            prompt=prompt,
            session_id=session_id,
        )

    if not out.get("ok"):
        code = str(out.get("code") or "VISION_FAILED")
        logger.warning("vision analyze failed: %s", code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_err(code, str(out.get("error") or "vision failed")),
        )
    return out


@router.post("/audio/transcribe")
async def audio_transcribe(
    _app_user_id: str = Depends(get_valid_web_user_id),
    audio: UploadFile | None = File(None),
) -> dict[str, Any]:
    _ = audio
    if not multimodal_globally_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_err("MULTIMODAL_DISABLED", "Set NEXA_MULTIMODAL_ENABLED=true"),
        )
    if not audio_input_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_err("AUDIO_INPUT_DISABLED", "Enable NEXA_AUDIO_INPUT_ENABLED when the master flag is on"),
        )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=_err("PHASE_18A_PLACEHOLDER", "Speech-to-text ships in Phase 18d"),
    )


class SpeechSynthesizeBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=12_000)
    voice: str | None = None


@router.post("/speech/synthesize")
async def speech_synthesize(
    payload: SpeechSynthesizeBody,
    _app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _ = payload
    if not multimodal_globally_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_err("MULTIMODAL_DISABLED", "Set NEXA_MULTIMODAL_ENABLED=true"),
        )
    if not audio_output_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_err("AUDIO_OUTPUT_DISABLED", "Enable NEXA_AUDIO_OUTPUT_ENABLED when the master flag is on"),
        )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=_err("PHASE_18A_PLACEHOLDER", "Text-to-speech ships in a later 18.x milestone"),
    )


class ImageGenerateBody(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    size: str | None = Field(default=None, max_length=32)
    n: int = Field(default=1, ge=1, le=10)


@router.post("/image/generate")
async def image_generate(
    payload: ImageGenerateBody,
    _app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _ = payload
    if not multimodal_globally_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_err("MULTIMODAL_DISABLED", "Set NEXA_MULTIMODAL_ENABLED=true"),
        )
    if not image_gen_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_err("IMAGE_GEN_DISABLED", "Enable NEXA_IMAGE_GEN_ENABLED when the master flag is on"),
        )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=_err("PHASE_18A_PLACEHOLDER", "Image generation ships in Phase 18e+"),
    )


__all__ = ["router"]
