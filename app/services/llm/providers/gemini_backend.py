# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Google Gemini generateContent (REST) — vision-capable, Phase 18b."""

from __future__ import annotations

import base64
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.services.llm.base import LLMProvider, Message, ModelInfo, Tool
from app.services.llm.content_parts import flatten_openai_content_to_text, parse_data_url

logger = logging.getLogger(__name__)


class GeminiBackend(LLMProvider):
    """Minimal REST backend for vision turns (no streaming tools)."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout: float = 120.0,
    ) -> None:
        self.logical_name = "gemini"
        self._api_key = api_key.strip()
        self._model = model.strip()
        self._timeout = timeout

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            id=self._model,
            name=self._model,
            provider="gemini",
            context_length=1_000_000,
            supports_tools=False,
            supports_streaming=False,
            supports_vision=True,
        )

    def complete_chat(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format_json: bool = False,
        tools: list[Tool] | None = None,
    ) -> str:
        _ = response_format_json
        if tools:
            logger.warning("gemini backend: tools ignored (Phase 18b)")
        parts = _messages_to_gemini_parts(messages)
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent?key={self._api_key}"
        )
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": temperature,
            },
        }
        if max_tokens is not None:
            body["generationConfig"]["maxOutputTokens"] = max_tokens
        with httpx.Client(timeout=self._timeout) as client:
            r = client.post(url, json=body)
            r.raise_for_status()
            data = r.json()
        return _extract_gemini_text(data)

    async def complete_chat_streaming(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format_json: bool = False,
        tools: list[Tool] | None = None,
    ) -> AsyncIterator[str]:
        text = self.complete_chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format_json=response_format_json,
            tools=tools,
        )
        yield text

    def validate_api_key(self) -> bool:
        return bool(self._api_key)


def _extract_gemini_text(data: dict[str, Any]) -> str:
    cands = data.get("candidates")
    if not isinstance(cands, list) or not cands:
        return ""
    c0 = cands[0] if cands else {}
    content = c0.get("content") if isinstance(c0, dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        return ""
    texts: list[str] = []
    for p in parts:
        if isinstance(p, dict) and isinstance(p.get("text"), str):
            texts.append(p["text"])
    return "\n".join(texts).strip()


def _messages_to_gemini_parts(messages: list[Message]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "system":
            t = flatten_openai_content_to_text(m.content)  # type: ignore[arg-type]
            if t:
                parts.append({"text": f"[system]\n{t}"})
            continue
        if m.role != "user":
            parts.append({"text": flatten_openai_content_to_text(m.content)})  # type: ignore[arg-type]
            continue
        c = m.content
        if isinstance(c, str):
            if c.strip():
                parts.append({"text": c})
            continue
        for b in c:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text":
                tx = (b.get("text") or "").strip()
                if tx:
                    parts.append({"text": tx})
            elif b.get("type") == "image_url":
                iu = b.get("image_url") or {}
                url = str((iu.get("url") if isinstance(iu, dict) else "") or "").strip()
                if url.startswith("data:"):
                    parsed = parse_data_url(url)
                    if parsed:
                        mime, raw = parsed
                        parts.append(
                            {
                                "inline_data": {
                                    "mime_type": mime,
                                    "data": base64.b64encode(raw).decode("ascii"),
                                }
                            }
                        )
                elif url.startswith("http://") or url.startswith("https://"):
                    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                        r = client.get(url)
                        r.raise_for_status()
                        b = r.content
                        rct = (r.headers.get("content-type") or "image/jpeg").split(";")[0].strip()
                    parts.append({"inline_data": {"mime_type": rct, "data": base64.b64encode(b).decode("ascii")}})
    if not parts:
        parts.append({"text": "Describe this image."})
    return parts
