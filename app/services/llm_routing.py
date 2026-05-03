"""Pro smart routing — optional ``nexa_ext.routing`` + ``smart_routing`` license."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.services.extensions import get_extension
from app.services.licensing.features import FEATURE_SMART_ROUTING, has_pro_feature


def map_pro_routing_model_key(symbolic: str) -> str:
    """Map extension symbolic tier → Anthropic model id from settings."""
    s = get_settings()
    default = (s.anthropic_model or "").strip() or "claude-haiku-4-5-20251001"
    key = (symbolic or "").strip().lower().replace("_", "-")

    if key in ("claude-strong", "claude_strong", "strong", "dev"):
        return getattr(s, "nexa_pro_anthropic_strong_model", None) or default
    if key in ("local-ollama", "local_ollama", "ollama", "fast", "cheap"):
        return getattr(s, "nexa_pro_anthropic_fast_model", None) or default
    if key in ("balanced", "default", "medium"):
        return default
    return default


def _infer_task_type(intent: str | None, behavior: str | None) -> str:
    i = (intent or "").strip().lower()
    b = (behavior or "").strip().lower()
    if i == "stuck_dev" or b == "unstick":
        return "dev"
    if i == "analysis":
        return "analysis"
    return "chat"


def _infer_complexity(user_message: str | None) -> str:
    t = (user_message or "").strip()
    return "low" if len(t) < 72 else "medium"


def resolve_anthropic_model_for_composer(ctx: Any | None) -> str:
    """Anthropic model id for composer LLM calls."""
    s = get_settings()
    default = (s.anthropic_model or "").strip() or "claude-haiku-4-5-20251001"
    if ctx is None:
        return default
    mod = get_extension("routing")
    if mod is None or not has_pro_feature(FEATURE_SMART_ROUTING):
        return default
    choose = getattr(mod, "choose_model", None)
    if not callable(choose):
        return default
    task_type = _infer_task_type(ctx.intent, ctx.behavior)
    complexity = _infer_complexity(ctx.user_message)
    budget = float(getattr(s, "nexa_cost_budget_per_day_usd", 5.0) or 5.0)
    try:
        sym = choose(task_type, complexity, budget)
    except Exception:
        return default
    return map_pro_routing_model_key(str(sym))


__all__ = ["map_pro_routing_model_key", "resolve_anthropic_model_for_composer"]
