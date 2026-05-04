"""Ollama /api/chat backend (Phase 11) — local HTTP, no OpenAI SDK."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.llm.base import LLMProvider, Message, ModelInfo, Tool

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
            "messages": [{"role": m.role, "content": m.content} for m in messages],
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
            return str(msg.get("content") or "").strip()
        return str(data.get("response") or "").strip()


__all__ = ["OllamaBackend"]
