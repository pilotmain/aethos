"""
Primary completion chain for :mod:`app.services.llm_service` (Phase 11).
"""

from __future__ import annotations

import logging
from typing import Callable

from app.core.config import get_settings
from app.services.llm.base import Message
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


__all__ = ["get_llm", "primary_complete_raw", "providers_available"]
