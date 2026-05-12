# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""OpenAI-style multimodal content blocks (Phase 18b) — shared by providers."""

from __future__ import annotations

import base64
import re
from typing import Any

# OpenAI Chat Completions "content" can be a string or a list of part dicts, e.g.:
# [{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "https://..."}}]


def text_block(text: str) -> dict[str, Any]:
    return {"type": "text", "text": (text or "").strip()}


def image_url_block(url: str, *, detail: str | None = "auto") -> dict[str, Any]:
    u = (url or "").strip()
    out: dict[str, Any] = {"type": "image_url", "image_url": {"url": u}}
    if detail:
        out["image_url"]["detail"] = detail
    return out


def image_data_url(mime: str, raw_bytes: bytes) -> str:
    m = (mime or "image/png").strip() or "image/png"
    b64 = base64.b64encode(raw_bytes).decode("ascii")
    return f"data:{m};base64,{b64}"


def image_base64_block(mime: str, raw_bytes: bytes, *, detail: str | None = "auto") -> dict[str, Any]:
    return image_url_block(image_data_url(mime, raw_bytes), detail=detail)


_DATA_URL_RE = re.compile(r"^data:(?P<mime>[\w.+-]+/[\w.+-]+);base64,(?P<b64>.+)$", re.DOTALL)


def parse_data_url(data_url: str) -> tuple[str, bytes] | None:
    m = _DATA_URL_RE.match((data_url or "").strip())
    if not m:
        return None
    mime = m.group("mime")
    try:
        raw = base64.b64decode(m.group("b64"), validate=True)
    except Exception:
        return None
    return mime, raw


def flatten_openai_content_to_text(content: str | list[dict[str, Any]]) -> str:
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for b in content:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t == "text" and isinstance(b.get("text"), str):
            parts.append(b["text"])
    return "\n".join(parts).strip()


def content_has_vision_part(content: str | list[dict[str, Any]]) -> bool:
    if isinstance(content, str):
        return False
    for b in content:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t == "image_url" and b.get("image_url"):
            return True
    return False
