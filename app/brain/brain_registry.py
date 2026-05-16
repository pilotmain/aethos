# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Available brains from settings (Phase 2 Step 7)."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.brain.brain_capabilities import REPAIR_PLAN_TASK, brain_supports_task


def _has_key(val: str | None) -> bool:
    return bool((val or "").strip())


def list_repair_brain_candidates(settings: Settings | None = None) -> list[dict[str, Any]]:
    """Ordered preference hints — final order applied in brain_selection."""
    s = settings or get_settings()
    out: list[dict[str, Any]] = []

    local_name = (s.aethos_local_model_name or s.nexa_ollama_default_model or "qwen2.5:7b").strip()
    if s.nexa_ollama_enabled or s.aethos_local_first_enabled or s.nexa_local_first:
        out.append(
            {
                "provider": "ollama",
                "model": local_name,
                "local": True,
                "available": bool(s.nexa_ollama_enabled),
            }
        )

    primary = (s.nexa_llm_provider or s.llm_provider or "anthropic").strip().lower()
    if primary == "openai" and _has_key(s.openai_api_key):
        out.append({"provider": "openai", "model": (s.openai_model or "gpt-4.1-mini"), "local": False, "available": True})
    elif primary in ("anthropic", "auto") and _has_key(s.anthropic_api_key):
        out.append(
            {
                "provider": "anthropic",
                "model": (s.anthropic_model or "claude-haiku-4-5-20251001"),
                "local": False,
                "available": True,
            }
        )
    elif _has_key(s.openai_api_key):
        out.append({"provider": "openai", "model": (s.openai_model or "gpt-4.1-mini"), "local": False, "available": True})
    elif _has_key(s.anthropic_api_key):
        out.append(
            {
                "provider": "anthropic",
                "model": (s.anthropic_model or "claude-haiku-4-5-20251001"),
                "local": False,
                "available": True,
            }
        )

    if _has_key(s.openai_api_key) and not any(r["provider"] == "openai" for r in out):
        out.append({"provider": "openai", "model": (s.openai_model or "gpt-4.1-mini"), "local": False, "available": True})
    if _has_key(s.anthropic_api_key) and not any(r["provider"] == "anthropic" for r in out):
        out.append(
            {
                "provider": "anthropic",
                "model": (s.anthropic_model or "claude-haiku-4-5-20251001"),
                "local": False,
                "available": True,
            }
        )

    out.append({"provider": "deterministic", "model": "deterministic-repair-v1", "local": True, "available": True})
    return [r for r in out if brain_supports_task(str(r["provider"]), REPAIR_PLAN_TASK)]
