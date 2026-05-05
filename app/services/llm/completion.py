"""
Primary completion chain for :mod:`app.services.llm_service` (Phase 11).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Callable

from app.core.config import get_settings
from app.services.budget.hooks import (
    budget_enabled,
    check_budget_before_llm,
    llm_preflight_estimate,
    record_budget_after_llm,
)
from app.services.llm.base import Message, Tool
from app.services.llm.bootstrap import register_llm_providers_from_settings
from app.services.llm.registry import get_llm_registry
from app.services.network_policy.policy import assert_provider_egress_allowed

logger = logging.getLogger(__name__)

_AUTO_ORDER = ("anthropic", "openai", "deepseek", "openrouter", "ollama")


def _parse_fallback_csv(raw: str) -> list[str]:
    return [p.strip().lower() for p in (raw or "").split(",") if p.strip()]


def _build_chain() -> list[str]:
    s = get_settings()
    reg = get_llm_registry()
    primary = (s.nexa_llm_provider or "auto").strip().lower()

    if primary in ("", "auto"):
        chain = [p for p in _AUTO_ORDER if reg.get_provider(p)]
        for p in _parse_fallback_csv(s.nexa_llm_fallback_providers):
            if p not in chain and reg.get_provider(p):
                chain.append(p)
        return chain

    fb = _parse_fallback_csv(s.nexa_llm_fallback_providers)
    chain = [primary]
    for p in fb:
        if p not in chain:
            chain.append(p)
    return chain


def _egress_map(provider_name: str) -> str:
    return provider_name.strip().lower()


def primary_complete_raw(
    user_prompt: str,
    *,
    response_format_json: bool,
    max_tokens: int,
    temperature: float,
) -> str:
    """Return assistant text for a single merged user prompt."""
    register_llm_providers_from_settings()
    reg = get_llm_registry()
    messages = [Message(role="user", content=user_prompt)]
    chain = _build_chain()
    if not chain:
        raise RuntimeError("No LLM providers registered (configure API keys or Ollama)")

    last_err: Exception | None = None
    for name in chain:
        prov = reg.get_provider(name)
        if not prov:
            continue
        eg = _egress_map(name)
        block = assert_provider_egress_allowed(eg, None)
        if block:
            logger.warning("LLM provider %s blocked by egress policy: %s", name, block)
            continue
        try:
            return prov.complete_chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format_json=response_format_json,
            )
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.warning("LLM provider %s failed: %s", name, exc)

    if last_err is not None:
        raise last_err
    raise RuntimeError("No LLM provider could handle the request (egress or missing keys)")


def primary_complete_messages(
    messages: list[Message],
    *,
    response_format_json: bool = False,
    max_tokens: int | None = None,
    temperature: float | None = None,
    tools: list[Tool] | None = None,
    anthropic_model_override: str | None = None,
    budget_member_id: str | None = None,
    budget_member_name: str | None = None,
) -> str:
    """Multi-message completion using the same provider chain as :func:`primary_complete_raw`."""
    register_llm_providers_from_settings()
    reg = get_llm_registry()
    s = get_settings()
    chain = _build_chain()
    if not chain:
        raise RuntimeError("No LLM providers registered (configure API keys or Ollama)")

    temp = temperature if temperature is not None else s.nexa_llm_temperature
    mt = max_tokens if max_tokens is not None else s.nexa_llm_max_tokens

    if budget_member_id and budget_enabled():
        ok, err = check_budget_before_llm(
            budget_member_id, llm_preflight_estimate(messages, mt)
        )
        if not ok:
            raise RuntimeError(
                (err or "Budget limit reached for this team member.").strip()
            )

    last_err: Exception | None = None
    for name in chain:
        prov = reg.get_provider(name)
        if not prov:
            continue
        if name == "anthropic" and (anthropic_model_override or "").strip():
            from app.services.llm.providers.anthropic_backend import AnthropicBackend

            if isinstance(prov, AnthropicBackend):
                prov = prov.clone_with_model(anthropic_model_override.strip())
        eg = _egress_map(name)
        block = assert_provider_egress_allowed(eg, None)
        if block:
            logger.warning("LLM provider %s blocked by egress policy: %s", name, block)
            continue
        try:
            out = prov.complete_chat(
                messages,
                temperature=temp,
                max_tokens=mt,
                response_format_json=response_format_json,
                tools=tools,
            )
            if budget_member_id and budget_enabled():
                record_budget_after_llm(
                    budget_member_id, messages, out, member_name=budget_member_name
                )
            return out
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.warning("LLM provider %s failed: %s", name, exc)

    if last_err is not None:
        raise last_err
    raise RuntimeError("No LLM provider could handle the request (egress or missing keys)")


async def primary_complete_streaming(
    messages: list[Message],
    *,
    response_format_json: bool = False,
    max_tokens: int | None = None,
    temperature: float | None = None,
    tools: list[Tool] | None = None,
    budget_member_id: str | None = None,
    budget_member_name: str | None = None,
) -> AsyncIterator[str]:
    """Stream assistant text using the primary chain and fallbacks."""
    register_llm_providers_from_settings()
    reg = get_llm_registry()
    s = get_settings()
    chain = _build_chain()
    if not chain:
        raise RuntimeError("No LLM providers registered (configure API keys or Ollama)")

    temp = temperature if temperature is not None else s.nexa_llm_temperature
    mt = max_tokens if max_tokens is not None else s.nexa_llm_max_tokens

    if budget_member_id and budget_enabled():
        ok, err = check_budget_before_llm(
            budget_member_id, llm_preflight_estimate(messages, mt)
        )
        if not ok:
            yield err or "⚠️ Budget limit reached for this team member."
            return

    last_err: Exception | None = None
    for name in chain:
        prov = reg.get_provider(name)
        if not prov:
            continue
        eg = _egress_map(name)
        block = assert_provider_egress_allowed(eg, None)
        if block:
            logger.warning("LLM provider %s blocked by egress policy: %s", name, block)
            continue
        try:
            buf: list[str] = []
            async for chunk in prov.complete_chat_streaming(
                messages,
                temperature=temp,
                max_tokens=mt,
                response_format_json=response_format_json,
                tools=tools,
            ):
                buf.append(chunk)
                yield chunk
            if budget_member_id and budget_enabled():
                record_budget_after_llm(
                    budget_member_id,
                    messages,
                    "".join(buf),
                    member_name=budget_member_name,
                    description="LLM streaming call",
                )
            return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.warning("LLM streaming provider %s failed: %s", name, exc)

    if last_err is not None:
        raise last_err
    raise RuntimeError("No LLM provider could handle the streaming request (egress or missing keys)")


def get_llm() -> Callable[[str], str] | None:
    """Return a simple ``(prompt)->text`` using the default registered provider, or None."""
    register_llm_providers_from_settings()
    prov = get_llm_registry().get_provider()
    if not prov:
        return None

    def _call(user_prompt: str) -> str:
        s = get_settings()
        return prov.complete_chat(
            [Message(role="user", content=user_prompt)],
            temperature=s.nexa_llm_temperature,
            max_tokens=s.nexa_llm_max_tokens,
            response_format_json=False,
        )

    return _call


def providers_available() -> bool:
    """True if at least one Phase 11 backend could be registered."""
    from app.services.llm_key_resolution import get_merged_api_keys

    s = get_settings()
    m = get_merged_api_keys()
    if m.anthropic_api_key or m.openai_api_key:
        return True
    if (s.deepseek_api_key or "").strip():
        return True
    if (s.openrouter_api_key or "").strip():
        return True
    p = (s.nexa_llm_provider or "").strip().lower()
    if (s.nexa_llm_api_key or "").strip() and p not in ("", "auto"):
        return True
    if s.nexa_ollama_enabled or p == "ollama":
        return True
    return False


__all__ = [
    "get_llm",
    "primary_complete_raw",
    "primary_complete_messages",
    "primary_complete_streaming",
    "providers_available",
]
