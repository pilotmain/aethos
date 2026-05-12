"""
Register :class:`~app.services.llm.base.LLMProvider` instances from settings and BYOK merge.
"""

from __future__ import annotations

import logging
from app.core.config import Settings, get_settings
from app.services.llm_key_resolution import MergedLlmKeyInfo, get_merged_api_keys
from app.services.llm.providers.anthropic_backend import AnthropicBackend
from app.services.llm.providers.ollama_backend import OllamaBackend
from app.services.llm.providers.openai_backend import OpenAIBackend
from app.services.llm.registry import LLMRegistry, get_llm_registry

logger = logging.getLogger(__name__)


def _resolve_api_key(provider_id: str, s: Settings, m: MergedLlmKeyInfo) -> str | None:
    primary = (s.nexa_llm_provider or "auto").strip().lower()
    if primary == provider_id and (s.nexa_llm_api_key or "").strip():
        return s.nexa_llm_api_key.strip()
    if provider_id == "openai":
        return (m.openai_api_key or s.openai_api_key or "").strip() or None
    if provider_id == "anthropic":
        return (m.anthropic_api_key or s.anthropic_api_key or "").strip() or None
    if provider_id == "deepseek":
        return (s.deepseek_api_key or "").strip() or None
    if provider_id == "openrouter":
        return (s.openrouter_api_key or "").strip() or None
    return None


def _resolve_model(provider_id: str, s: Settings, *, is_primary_target: bool) -> str:
    primary = (s.nexa_llm_provider or "auto").strip().lower()
    if is_primary_target and (s.nexa_llm_model or "").strip() and primary == provider_id:
        return s.nexa_llm_model.strip()
    if provider_id == "anthropic":
        from app.services.llm_intelligence import resolve_effective_anthropic_model_id

        return resolve_effective_anthropic_model_id(s)
    if provider_id == "openai":
        return s.openai_model
    if provider_id == "deepseek":
        return s.deepseek_model
    if provider_id == "openrouter":
        return s.openrouter_model
    if provider_id == "ollama":
        return s.nexa_ollama_default_model
    return ""


def register_llm_providers_from_settings() -> LLMRegistry:
    """Idempotent registration keyed off cached Settings."""
    reg = get_llm_registry()
    if reg.initialized:
        return reg

    s = get_settings()
    m = get_merged_api_keys()
    timeout = float(s.nexa_provider_timeout_seconds or 120.0)
    primary = (s.nexa_llm_provider or "auto").strip().lower()

    def primary_is(pid: str) -> bool:
        return primary == pid

    # Anthropic
    ak = _resolve_api_key("anthropic", s, m)
    if ak:
        reg.register(
            "anthropic",
            AnthropicBackend(
                api_key=ak,
                model=_resolve_model("anthropic", s, is_primary_target=primary_is("anthropic")),
                timeout=timeout,
                used_user_key=m.has_user_anthropic,
            ),
            set_default=primary_is("anthropic"),
        )

    # OpenAI
    ok = _resolve_api_key("openai", s, m)
    if ok:
        base_url = None
        if primary_is("openai") and (s.nexa_llm_base_url or "").strip():
            base_url = s.nexa_llm_base_url.strip()
        reg.register(
            "openai",
            OpenAIBackend(
                logical_name="openai",
                api_key=ok,
                model=_resolve_model("openai", s, is_primary_target=primary_is("openai")),
                base_url=base_url,
                timeout=timeout,
                usage_provider="openai",
                used_user_key=m.has_user_openai,
            ),
            set_default=primary_is("openai"),
        )

    # DeepSeek (OpenAI-compatible)
    dk = _resolve_api_key("deepseek", s, m)
    if dk:
        d_base = (s.deepseek_base_url or "").strip() or "https://api.deepseek.com/v1"
        reg.register(
            "deepseek",
            OpenAIBackend(
                logical_name="deepseek",
                api_key=dk,
                model=_resolve_model("deepseek", s, is_primary_target=primary_is("deepseek")),
                base_url=d_base,
                timeout=timeout,
                usage_provider="deepseek",
                used_user_key=False,
            ),
            set_default=primary_is("deepseek"),
        )

    # OpenRouter
    or_key = _resolve_api_key("openrouter", s, m)
    if or_key:
        or_base = (s.openrouter_base_url or "").strip() or "https://openrouter.ai/api/v1"
        reg.register(
            "openrouter",
            OpenAIBackend(
                logical_name="openrouter",
                api_key=or_key,
                model=_resolve_model("openrouter", s, is_primary_target=primary_is("openrouter")),
                base_url=or_base,
                timeout=timeout,
                usage_provider="openrouter",
                used_user_key=False,
            ),
            set_default=primary_is("openrouter"),
        )

    # Ollama — register when explicitly chosen or local-first flags encourage it
    want_ollama = primary_is("ollama") or s.nexa_ollama_enabled or (
        primary == "auto" and getattr(s, "nexa_local_first", False)
    )
    if want_ollama:
        base = (s.nexa_ollama_base_url or "").strip() or "http://127.0.0.1:11434"
        reg.register(
            "ollama",
            OllamaBackend(
                base_url=base,
                model=_resolve_model("ollama", s, is_primary_target=primary_is("ollama")),
                timeout=timeout,
            ),
            set_default=primary_is("ollama"),
        )

    if primary not in ("auto", "") and not reg.get_provider(primary):
        logger.warning(
            "NEXA_LLM_PROVIDER=%s but that provider is not registered (missing keys?)",
            primary,
        )

    reg.mark_initialized()
    logger.info(
        "LLM registry initialized providers=%s default=%s",
        sorted(reg._providers.keys()),
        getattr(reg, "_default_name", None),
    )
    return reg


__all__ = ["register_llm_providers_from_settings"]
