# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Provider catalog (Phase 52) — document OpenAI-compatible and regional options.

Runtime routing may grow into this module; today it is the source of truth for IDs and env keys.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Region = Literal["us", "europe", "china", "local", "global"]


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    region: Region
    api_style: str
    env_keys: tuple[str, ...] = field(default_factory=tuple)
    base_url_env: str | None = None
    privacy_note: str = "Bring your own key; no provider call without user configuration."


# Curated list — expand with NEXA_PROVIDER_* env wiring in future PRs.
PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec("openai", "us", "openai_native", ("OPENAI_API_KEY",)),
    ProviderSpec("anthropic", "us", "anthropic_native", ("ANTHROPIC_API_KEY",)),
    ProviderSpec("gemini", "global", "google", ("GOOGLE_API_KEY",)),
    ProviderSpec("groq", "us", "openai_compatible", ("GROQ_API_KEY",), base_url_env="GROQ_BASE_URL"),
    ProviderSpec("openrouter", "global", "openai_compatible", ("OPENROUTER_API_KEY",), base_url_env="OPENROUTER_BASE_URL"),
    ProviderSpec("mistral", "europe", "openai_compatible", ("MISTRAL_API_KEY",)),
    ProviderSpec("deepseek", "china", "openai_compatible", ("DEEPSEEK_API_KEY",), base_url_env="DEEPSEEK_BASE_URL"),
    ProviderSpec("dashscope", "china", "openai_compatible", ("DASHSCOPE_API_KEY",)),
    ProviderSpec("ollama", "local", "openai_compatible", (), base_url_env="OLLAMA_BASE_URL"),
    ProviderSpec("lmstudio", "local", "openai_compatible", (), base_url_env="LMSTUDIO_BASE_URL"),
)


def choose_provider_for_task(
    *,
    task_kind: str | None = None,
    user_settings: dict[str, Any] | None = None,
    local_first: bool = True,
) -> str:
    """
    Minimal deterministic router placeholder — prefers local when ``local_first`` and configured.

    Extend with settings-backed preference (``preferred_provider``, ``provider_region_preference``).
    """
    _ = task_kind
    prefs = user_settings or {}
    explicit = str(prefs.get("preferred_provider") or "").strip().lower()
    if explicit:
        return explicit[:64]
    if local_first:
        return "ollama"
    return "openai"


def providers_by_region(region: Region) -> tuple[ProviderSpec, ...]:
    return tuple(p for p in PROVIDERS if p.region == region or p.region == "global")


__all__ = ["PROVIDERS", "ProviderSpec", "choose_provider_for_task", "providers_by_region"]
