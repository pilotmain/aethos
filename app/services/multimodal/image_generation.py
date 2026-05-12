# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Image generation — OpenAI DALL-E, Replicate (SD/FLUX), optional local A1111 (Phase 18d)."""

from __future__ import annotations

import base64
import logging
import time
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.services.llm_key_resolution import get_merged_api_keys
from app.services.network_policy.policy import assert_provider_egress_allowed, is_egress_allowed

logger = logging.getLogger(__name__)


def generate_images(
    prompt: str,
    *,
    size: str | None = None,
    quality: str | None = None,
    n: int = 1,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """
    Return ``{ok, images: [{url?|b64_json?}], model, provider}`` or ``{ok: False, code, error}``.
    """
    s = settings or get_settings()
    p = (s.nexa_image_gen_provider or "openai").strip().lower()
    if p in ("replicate", "rep"):
        return _replicate_generate(prompt, size=size, n=n, settings=s)
    if p in ("local_sd", "local", "a1111", "stable_diffusion_local"):
        return _local_a1111_generate(prompt, size=size, n=n, settings=s)
    return _openai_dalle_generate(prompt, size=size, quality=quality, n=n, settings=s)


def _resolve_openai_key(st: Settings) -> str | None:
    m = get_merged_api_keys()
    return (m.openai_api_key or st.openai_api_key or st.nexa_llm_api_key or "").strip() or None


def _openai_dalle_generate(
    prompt: str,
    *,
    size: str | None,
    quality: str | None,
    n: int,
    settings: Settings,
) -> dict[str, Any]:
    block = assert_provider_egress_allowed("openai", None)
    if block:
        return {"ok": False, "code": "EGRESS_BLOCKED", "error": block}
    key = _resolve_openai_key(settings)
    if not key:
        return {"ok": False, "code": "MISSING_OPENAI_KEY", "error": "Configure OpenAI API key for DALL-E"}

    model = (settings.nexa_openai_image_model or "dall-e-3").strip().lower()
    if model not in ("dall-e-2", "dall-e-3"):
        model = "dall-e-3"

    n_req = max(1, min(int(n or 1), 10))
    if model == "dall-e-3":
        n_req = 1
    sz = (size or "1024x1024").strip()
    q = (quality or "standard").strip().lower()
    if q not in ("standard", "hd"):
        q = "standard"

    body: dict[str, Any] = {
        "model": model,
        "prompt": prompt[:8000],
        "n": n_req,
        "response_format": "url",
    }
    if model == "dall-e-3":
        body["size"] = sz if sz in ("1024x1024", "1792x1024", "1024x1792") else "1024x1024"
        body["quality"] = q
    else:
        body["size"] = sz if sz in ("256x256", "512x512", "1024x1024") else "1024x1024"

    url = "https://api.openai.com/v1/images/generations"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=180.0) as client:
            r = client.post(url, headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("openai image generation failed: %s", exc)
        return {"ok": False, "code": "IMAGE_GEN_FAILED", "error": str(exc)[:1000]}

    out_imgs: list[dict[str, str]] = []
    for it in data.get("data") or []:
        if isinstance(it, dict):
            u = it.get("url")
            b64 = it.get("b64_json")
            if u:
                out_imgs.append({"url": str(u)})
            elif b64:
                out_imgs.append({"b64_json": str(b64)})
    if not out_imgs:
        return {"ok": False, "code": "EMPTY_RESULT", "error": "No image URLs returned"}
    return {"ok": True, "images": out_imgs, "model": model, "provider": "openai"}


def _replicate_generate(
    prompt: str,
    *,
    size: str | None,
    n: int,
    settings: Settings,
) -> dict[str, Any]:
    block = assert_provider_egress_allowed("replicate", None)
    if block:
        return {"ok": False, "code": "EGRESS_BLOCKED", "error": block}
    token = (settings.nexa_replicate_api_token or "").strip()
    if not token:
        return {"ok": False, "code": "MISSING_REPLICATE_TOKEN", "error": "Set NEXA_REPLICATE_API_TOKEN"}
    version = (settings.nexa_replicate_image_version or "").strip()
    if not version:
        return {
            "ok": False,
            "code": "MISSING_REPLICATE_VERSION",
            "error": "Set NEXA_REPLICATE_IMAGE_VERSION to a model version hash",
        }

    _ = (size, n)  # Replicate model I/O varies; v1 uses `input.prompt` only (size/n in model config).

    create_url = "https://api.replicate.com/v1/predictions"
    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
    payload: dict[str, Any] = {
        "version": version,
        "input": {
            "prompt": prompt[:8000],
        },
    }
    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(create_url, headers=headers, json=payload)
            r.raise_for_status()
            pred = r.json()
            pred_id = str(pred.get("id") or "")
            poll_url = str(pred.get("urls", {}).get("get") or "") or f"{create_url}/{pred_id}"
            out = _poll_replicate(client, headers, poll_url, timeout_s=150.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("replicate image generation failed: %s", exc)
        return {"ok": False, "code": "IMAGE_GEN_FAILED", "error": str(exc)[:1000]}

    images = _replicate_output_to_images(out)
    if not images:
        return {"ok": False, "code": "EMPTY_RESULT", "error": "Replicate returned no image URLs"}
    return {"ok": True, "images": images, "model": version[:24], "provider": "replicate"}


def _poll_replicate(
    client: httpx.Client,
    headers: dict[str, str],
    poll_url: str,
    *,
    timeout_s: float,
) -> Any:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        pr = client.get(poll_url, headers=headers, timeout=30.0)
        pr.raise_for_status()
        data = pr.json()
        st = str(data.get("status") or "").lower()
        if st in ("succeeded", "success"):
            return data.get("output")
        if st in ("failed", "canceled", "cancelled"):
            err = data.get("error") or data
            raise RuntimeError(str(err)[:800])
        if st not in ("starting", "processing", "queued", ""):
            logger.debug("replicate unexpected status=%s", st)
        time.sleep(1.5)
    raise TimeoutError("Replicate prediction timed out")


def _replicate_output_to_images(output: Any) -> list[dict[str, str]]:
    urls: list[str] = []

    def _walk(obj: Any) -> None:
        if isinstance(obj, str) and obj.startswith("http"):
            urls.append(obj)
        elif isinstance(obj, list):
            for x in obj:
                _walk(x)
        elif isinstance(obj, dict):
            u = obj.get("url")
            if isinstance(u, str) and u.startswith("http"):
                urls.append(u)
            else:
                for v in obj.values():
                    _walk(v)

    _walk(output)
    return [{"url": u} for u in urls]


def _parse_size_wh(size: str | None, *, default_w: int, default_h: int) -> tuple[int, int]:
    if not size or "x" not in (size or "").lower():
        return default_w, default_h
    parts = size.lower().replace(" ", "").split("x", 1)
    try:
        w = int(parts[0])
        h = int(parts[1])
        return max(64, min(w, 2048)), max(64, min(h, 2048))
    except (ValueError, IndexError):
        return default_w, default_h


def _local_a1111_generate(
    prompt: str,
    *,
    size: str | None,
    n: int,
    settings: Settings,
) -> dict[str, Any]:
    raw_url = (settings.nexa_local_sd_url or "").strip()
    if not raw_url:
        return {"ok": False, "code": "MISSING_LOCAL_SD_URL", "error": "Set NEXA_LOCAL_SD_URL (A1111 txt2img endpoint)"}
    if not is_egress_allowed(raw_url, purpose="local_sd", user_id=None):
        return {"ok": False, "code": "EGRESS_BLOCKED", "error": "network_egress_blocked"}

    w, h = _parse_size_wh(size, default_w=512, default_h=512)
    n_img = max(1, min(int(n or 1), 4))
    body = {
        "prompt": prompt[:8000],
        "steps": 20,
        "width": w,
        "height": h,
        "batch_size": n_img,
    }
    try:
        with httpx.Client(timeout=300.0) as client:
            r = client.post(raw_url, json=body)
            r.raise_for_status()
            data = r.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("local SD generation failed: %s", exc)
        return {"ok": False, "code": "IMAGE_GEN_FAILED", "error": str(exc)[:1000]}

    imgs_raw = data.get("images") if isinstance(data, dict) else None
    if not isinstance(imgs_raw, list):
        return {"ok": False, "code": "EMPTY_RESULT", "error": "Local SD returned no images"}

    out_imgs: list[dict[str, str]] = []
    for b64 in imgs_raw:
        if isinstance(b64, str) and b64.strip():
            out_imgs.append({"b64_json": b64.strip()})
    if not out_imgs:
        return {"ok": False, "code": "EMPTY_RESULT", "error": "No base64 images in response"}
    return {"ok": True, "images": out_imgs, "model": "local_sd", "provider": "local_sd"}


def first_image_payload_for_telegram(result: dict[str, Any]) -> tuple[str | None, bytes | None]:
    """Return ``(url, png_bytes)`` for the first generated image."""
    if not result.get("ok"):
        return None, None
    for img in result.get("images") or []:
        if not isinstance(img, dict):
            continue
        u = img.get("url")
        if u:
            return str(u), None
        b64 = img.get("b64_json")
        if b64:
            try:
                return None, base64.b64decode(str(b64), validate=False)
            except Exception:  # noqa: BLE001
                continue
    return None, None


__all__ = ["first_image_payload_for_telegram", "generate_images"]
