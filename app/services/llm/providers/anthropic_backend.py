"""Anthropic Messages API backend (Phase 11)."""

from __future__ import annotations

import logging
from typing import Any

from app.services.llm.base import LLMProvider, Message, ModelInfo, Tool
from app.services.llm_usage_recorder import record_anthropic_message_usage
from app.services.providers.sdk import build_anthropic_client

logger = logging.getLogger(__name__)


class AnthropicBackend(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout: float = 120.0,
        used_user_key: bool = False,
    ) -> None:
        self.logical_name = "anthropic"
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._used_user_key = used_user_key

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            id=self._model,
            name=self._model,
            provider="anthropic",
            context_length=200_000,
            supports_tools=True,
            supports_streaming=True,
            supports_vision="vision" in self._model.lower() or "4" in self._model,
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
            logger.warning("anthropic backend: tool list passed but not wired in Phase 11 minimal path")
        system, user_content = _split_system_user(messages)
        max_tok = max_tokens if max_tokens is not None else 4096
        client = build_anthropic_client(api_key=self._api_key, timeout=self._timeout)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tok,
            "temperature": temperature,
            "messages": [{"role": "user", "content": user_content}],
        }
        if system:
            kwargs["system"] = system
        msg = client.messages.create(**kwargs)
        try:
            record_anthropic_message_usage(
                msg,
                model=self._model,
                used_user_key=self._used_user_key,
            )
        except Exception:  # noqa: BLE001
            pass
        parts: list[str] = []
        for block in msg.content:
            t = getattr(block, "text", None)
            if t:
                parts.append(t)
        return "".join(parts).strip()


def _split_system_user(messages: list[Message]) -> tuple[str, str]:
    sys_chunks: list[str] = []
    user_chunks: list[str] = []
    for m in messages:
        if m.role == "system":
            sys_chunks.append(m.content)
        elif m.role == "user":
            user_chunks.append(m.content)
        elif m.role == "assistant":
            user_chunks.append(f"[assistant]: {m.content}")
        else:
            user_chunks.append(f"[{m.role}]: {m.content}")
    return "\n".join(sys_chunks).strip(), "\n\n".join(user_chunks).strip() or " "


__all__ = ["AnthropicBackend"]
