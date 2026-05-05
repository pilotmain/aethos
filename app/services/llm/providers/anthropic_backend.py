"""Anthropic Messages API backend (Phase 11) — Phase 18b vision blocks."""

from __future__ import annotations

import base64
import logging
from collections.abc import AsyncIterator
from typing import Any

from app.services.llm.base import LLMProvider, Message, ModelInfo, Tool
from app.services.llm.content_parts import flatten_openai_content_to_text, parse_data_url
from app.services.llm_usage_recorder import record_anthropic_message_usage
from app.services.providers.sdk import build_async_anthropic_client, build_anthropic_client

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

    def clone_with_model(self, model: str) -> AnthropicBackend:
        """Return a copy using ``model`` (composer smart-routing override)."""
        return AnthropicBackend(
            api_key=self._api_key,
            model=model.strip(),
            timeout=self._timeout,
            used_user_key=self._used_user_key,
        )

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
        system_text, api_messages = messages_to_anthropic(messages)
        max_tok = max_tokens if max_tokens is not None else 4096
        client = build_anthropic_client(api_key=self._api_key, timeout=self._timeout)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tok,
            "temperature": temperature,
            "messages": api_messages,
        }
        if system_text:
            kwargs["system"] = system_text
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
            logger.warning("anthropic backend: streaming with tools not wired in Phase 11.5 minimal path")
        system_text, api_messages = messages_to_anthropic(messages)
        max_tok = max_tokens if max_tokens is not None else 4096
        client = build_async_anthropic_client(api_key=self._api_key, timeout=self._timeout)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tok,
            "temperature": temperature,
            "messages": api_messages,
        }
        if system_text:
            kwargs["system"] = system_text
        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text
            try:
                final = await stream.get_final_message()
                record_anthropic_message_usage(
                    final,
                    model=self._model,
                    used_user_key=self._used_user_key,
                )
            except Exception:  # noqa: BLE001
                pass


def messages_to_anthropic(messages: list[Message]) -> tuple[str, list[dict[str, Any]]]:
    """Split system vs Anthropic ``messages`` payload (multi-turn + vision)."""
    sys_chunks: list[str] = []
    api_messages: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "system":
            sys_chunks.append(flatten_openai_content_to_text(m.content))
        elif m.role == "user":
            api_messages.append({"role": "user", "content": openai_user_content_to_anthropic(m.content)})
        elif m.role == "assistant":
            api_messages.append({"role": "assistant", "content": flatten_openai_content_to_text(m.content)})
        else:
            api_messages.append(
                {
                    "role": "user",
                    "content": f"[{m.role}]: {flatten_openai_content_to_text(m.content)}",
                }
            )
    if not api_messages:
        api_messages = [{"role": "user", "content": " "}]
    return "\n".join(sys_chunks).strip(), api_messages


def openai_user_content_to_anthropic(content: str | list[dict[str, Any]]) -> str | list[dict[str, Any]]:
    if isinstance(content, str):
        t = content.strip()
        return t or " "
    out: list[dict[str, Any]] = []
    for b in content:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t == "text":
            tx = (b.get("text") or "").strip()
            if tx:
                out.append({"type": "text", "text": tx})
        elif t == "image_url":
            iu = b.get("image_url") or {}
            url = str((iu.get("url") if isinstance(iu, dict) else "") or "").strip()
            if url.startswith("data:"):
                parsed = parse_data_url(url)
                if parsed:
                    mime, raw = parsed
                    out.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime,
                                "data": base64.b64encode(raw).decode("ascii"),
                            },
                        }
                    )
            elif url:
                out.append({"type": "image", "source": {"type": "url", "url": url}})
    if not out:
        return " "
    if len(out) == 1 and out[0].get("type") == "text":
        return str(out[0].get("text") or " ")
    return out


__all__ = ["AnthropicBackend", "messages_to_anthropic", "openai_user_content_to_anthropic"]
