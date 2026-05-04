"""OpenAI Chat Completions backend (Phase 11)."""

from __future__ import annotations

import logging
from typing import Any

from app.services.llm.base import LLMProvider, Message, ModelInfo, Tool
from app.services.llm_usage_context import resolve_db_for_usage
from app.services.llm_usage_recorder import _tok_from_openai_response, record_llm_usage
from app.services.providers.sdk import build_openai_client

logger = logging.getLogger(__name__)


class OpenAIBackend(LLMProvider):
    """OpenAI (or any OpenAI-compatible HTTP API with the official SDK)."""

    def __init__(
        self,
        *,
        logical_name: str,
        api_key: str,
        model: str,
        base_url: str | None = None,
        timeout: float = 120.0,
        usage_provider: str = "openai",
        used_user_key: bool = False,
    ) -> None:
        self.logical_name = logical_name
        self._api_key = api_key
        self._model = model
        self._base_url = (base_url or "").strip() or None
        self._timeout = timeout
        self._usage_provider = (usage_provider or logical_name or "openai").strip().lower()
        self._used_user_key = used_user_key

    def get_model_info(self) -> ModelInfo:
        m = self._model
        ctx = 128_000 if "gpt-4" in m or "o1" in m or "o3" in m else 16_384
        return ModelInfo(
            id=m,
            name=m,
            provider="openai",
            context_length=ctx,
            supports_tools=True,
            supports_streaming=True,
            supports_vision="vision" in m or "4o" in m,
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
        payload_messages = self._to_openai_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": payload_messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if response_format_json:
            kwargs["response_format"] = {"type": "json_object"}
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
        client_kw: dict[str, Any] = {"api_key": self._api_key, "timeout": self._timeout}
        if self._base_url:
            client_kw["base_url"] = self._base_url
        client = build_openai_client(**client_kw)
        resp = client.chat.completions.create(**kwargs)
        choice = resp.choices[0].message
        text = (choice.content or "").strip()
        try:
            it, ot, _tot = _tok_from_openai_response(resp)
            record_llm_usage(
                resolve_db_for_usage(),
                provider=self._usage_provider,
                model=self._model,
                input_tokens=it,
                output_tokens=ot,
                used_user_key=self._used_user_key,
            )
        except Exception:  # noqa: BLE001
            pass
        return text

    @staticmethod
    def _to_openai_messages(messages: list[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for msg in messages:
            row: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.name:
                row["name"] = msg.name
            if msg.tool_calls is not None:
                row["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                row["tool_call_id"] = msg.tool_call_id
            out.append(row)
        return out


__all__ = ["OpenAIBackend"]
