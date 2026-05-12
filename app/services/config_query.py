# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 77 — answer natural-language questions about AethOS runtime configuration.

Reads :class:`~app.core.config.Settings` only; never echoes secret values.
"""

from __future__ import annotations

from app.core.config import Settings, get_settings


def _effective_llm_summary(settings: Settings) -> tuple[str, str, str]:
    """Return (provider_line, model_line, hint) for the primary routing/composer chain."""
    prov = (settings.nexa_llm_provider or "auto").strip() or "auto"
    explicit = (settings.nexa_llm_model or "").strip()

    if explicit:
        return (
            prov,
            explicit,
            "Set explicitly via `NEXA_LLM_MODEL` (and optionally `NEXA_LLM_PROVIDER`).",
        )

    # Typical composer chain: Anthropic first when key present, else OpenAI, etc.
    if settings.anthropic_api_key:
        from app.services.llm_intelligence import resolve_effective_anthropic_model_id

        mid = resolve_effective_anthropic_model_id(settings)
        if bool(getattr(settings, "nexa_llm_intelligence_apply_to_anthropic", True)):
            hint = (
                f"Anthropic model from `NEXA_LLM_INTELLIGENCE_LEVEL={settings.nexa_llm_intelligence_level}` "
                "(set `NEXA_LLM_INTELLIGENCE_APPLY_TO_ANTHROPIC=false` to use `ANTHROPIC_MODEL` only)."
            )
        else:
            hint = "Composer uses `ANTHROPIC_MODEL` when `ANTHROPIC_API_KEY` is set."
        return (prov, mid, hint)
    if settings.openai_api_key:
        return (
            prov,
            (settings.openai_model or "").strip() or "(openai default)",
            "Composer uses `OPENAI_MODEL` when `OPENAI_API_KEY` is set.",
        )
    if settings.deepseek_api_key:
        return (
            prov,
            (settings.deepseek_model or "").strip() or "deepseek-chat",
            "DeepSeek via `DEEPSEEK_MODEL` when configured.",
        )
    return (
        prov,
        "(no provider key detected — configure at least one LLM API key)",
        "Add keys in `.env` (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, …).",
    )


def handle_config_query(user_input: str) -> str:
    """Format a reply for configuration-related questions (sync; gateway-safe)."""
    settings = get_settings()
    user_lower = (user_input or "").lower()

    if any(
        k in user_lower
        for k in (
            "model",
            "llm",
            "provider",
            "anthropic",
            "openai",
            "deepseek",
            "ollama",
            "claude",
            "gpt",
        )
    ):
        prov, model_line, hint = _effective_llm_summary(settings)
        return (
            "**LLM configuration (this process)**\n\n"
            f"- Routing preference: `{prov}`\n"
            f"- Effective model head: `{model_line}`\n\n"
            f"_{hint}_\n\n"
            "To override explicitly, set `NEXA_LLM_PROVIDER` and `NEXA_LLM_MODEL` in `.env`."
        )

    if any(k in user_lower for k in ("workspace", "repository", "repo path", "work root", "path")):
        work = str(settings.host_executor_work_root or "").strip()
        ws = str(settings.nexa_workspace_root or "").strip()
        return (
            "**Workspace paths**\n\n"
            f"- Host executor work root: `{work or 'not set'}` (`HOST_EXECUTOR_WORK_ROOT`)\n"
            f"- Projects / workspace root: `{ws or 'not set'}` (`NEXA_WORKSPACE_ROOT`)\n\n"
            "Adjust both in `.env` if you need a different checkout or sandbox."
        )

    if any(k in user_lower for k in ("api key", "token", "credentials")):
        openai_ok = bool(settings.openai_api_key)
        anthropic_ok = bool(settings.anthropic_api_key)
        deepseek_ok = bool(settings.deepseek_api_key)
        openrouter_ok = bool(settings.openrouter_api_key)
        nexa_llm_ok = bool((settings.nexa_llm_api_key or "").strip())
        return (
            "**API key status (set / not set only)**\n\n"
            f"- Anthropic: {'configured' if anthropic_ok else 'not set'}\n"
            f"- OpenAI: {'configured' if openai_ok else 'not set'}\n"
            f"- DeepSeek: {'configured' if deepseek_ok else 'not set'}\n"
            f"- OpenRouter: {'configured' if openrouter_ok else 'not set'}\n"
            f"- `NEXA_LLM_API_KEY`: {'configured' if nexa_llm_ok else 'not set'}\n\n"
            "Values live in `.env` and are never repeated in chat."
        )

    prov2, model2, _ = _effective_llm_summary(settings)
    orch = "enabled" if settings.nexa_agent_orchestration_enabled else "disabled"
    heal = "enabled" if settings.nexa_self_healing_enabled else "disabled"
    gh_improve = "enabled" if settings.nexa_self_improvement_github_enabled else "disabled"
    sim = "enabled" if getattr(settings, "nexa_simulation_enabled", True) else "disabled"
    return (
        "**AethOS configuration summary**\n\n"
        f"- LLM routing: `{prov2}` · effective model: `{model2}`\n"
        f"- Host work root: `{settings.host_executor_work_root}`\n"
        f"- Workspace root: `{settings.nexa_workspace_root}`\n"
        f"- Agent orchestration: `{orch}`\n"
        f"- Self-healing supervisor: `{heal}`\n"
        f"- Self-improvement GitHub flow: `{gh_improve}`\n"
        f"- Simulation / approvals preview: `{sim}`\n\n"
        "See `.env` and `app/core/config.py` for the full matrix."
    )
