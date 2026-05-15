# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Ollama /api/chat backend (Phase 11) — local HTTP, no OpenAI SDK."""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.services.llm.base import LLMProvider, Message, ModelInfo, Tool
from app.services.llm.content_parts import flatten_openai_content_to_text, parse_data_url
from app.services.llm_usage_recorder import record_llm_usage

logger = logging.getLogger(__name__)


class OllamaBackend(LLMProvider):
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: float = 120.0,
    ) -> None:
        self.logical_name = "ollama"
        self._root = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def get_model_info(self) -> ModelInfo:
        m = self._model
        return ModelInfo(
            id=m,
            name=m,
            provider="ollama",
            context_length=8192,
            supports_tools=False,
            supports_streaming=True,
            supports_vision="llava" in m.lower() or "vision" in m.lower(),
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
            logger.warning("ollama backend: tools ignored in Phase 11 minimal path")
        url = f"{self._root}/api/chat"
        body: dict[str, Any] = {
            "model": self._model,
            "messages": _to_ollama_messages(messages),
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens is not None:
            body["options"]["num_predict"] = max_tokens
        try:
            with httpx.Client(timeout=self._timeout) as client:
                r = client.post(url, json=body)
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("ollama chat failed: %s", exc)
            raise
        msg = data.get("message") if isinstance(data, dict) else None
        if isinstance(msg, dict):
            out = str(msg.get("content") or "").strip()
        else:
            out = str(data.get("response") or "").strip()
        if isinstance(data, dict):
            self._record_chat_usage(data, success=True)
        return out

    def _record_chat_usage(self, data: dict[str, Any], *, success: bool, error_type: str | None = None) -> None:
        """Persist per-request usage so web chat can show provider/model (``build_usage_summary_for_request``)."""
        try:
            it = int(data.get("prompt_eval_count") or 0)
            ot = int(data.get("eval_count") or 0)
            record_llm_usage(
                None,
                provider="ollama",
                model=self._model,
                input_tokens=it,
                output_tokens=ot,
                used_user_key=False,
                success=success,
                error_type=error_type,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("ollama usage record skipped: %s", exc)

    async def complete_chat_streaming(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format_json: bool = False,
        tools: list[Tool] | None = None,
    ) -> AsyncIterator[str]:
        _ = response_format_json
        if tools:
            logger.warning("ollama backend: streaming with tools not wired in Phase 11.5 minimal path")
        url = f"{self._root}/api/chat"
        body: dict[str, Any] = {
            "model": self._model,
            "messages": _to_ollama_messages(messages),
            "stream": True,
            "options": {"temperature": temperature},
        }
        if max_tokens is not None:
            body["options"]["num_predict"] = max_tokens
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream("POST", url, json=body) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = data.get("message") if isinstance(data, dict) else None
                    if isinstance(msg, dict):
                        piece = msg.get("content") or ""
                        if piece:
                            yield str(piece)


def _to_ollama_messages(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if isinstance(m.content, str):
            out.append({"role": m.role, "content": m.content})
            continue
        if m.role != "user":
            out.append({"role": m.role, "content": flatten_openai_content_to_text(m.content)})
            continue
        # OpenAI-style multimodal (user): text + image_url (data URL or http)
        texts: list[str] = []
        b64_images: list[str] = []
        for b in m.content:
            if not isinstance(b, dict):
                continue
            t = b.get("type")
            if t == "text" and isinstance(b.get("text"), str):
                texts.append(b["text"].strip())
            elif t == "image_url":
                iu = b.get("image_url") or {}
                url = str((iu.get("url") if isinstance(iu, dict) else "") or "").strip()
                if url.startswith("data:"):
                    parsed = parse_data_url(url)
                    if parsed:
                        _mime, raw = parsed
                        b64_images.append(base64.b64encode(raw).decode("ascii"))
                elif url.startswith("http://") or url.startswith("https://"):
                    try:
                        import httpx

                        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                            r = client.get(url)
                            r.raise_for_status()
                            b64_images.append(base64.b64encode(r.content).decode("ascii"))
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("ollama: could not fetch image url: %s", exc)
        row: dict[str, Any] = {"role": m.role, "content": "\n".join(texts).strip() or "Describe this image."}
        if b64_images:
            row["images"] = b64_images
        out.append(row)
    return out


__all__ = ["OllamaBackend"]
