"""Phase 55 — centralized policy for when Nexa should execute vs stay in suggestion mode."""

from __future__ import annotations

from typing import Literal

from app.core.config import get_settings
from app.services.execution_policy import (
    assess_interaction_risk,
    contains_destructive_language,
    should_auto_execute_dev_turn,
    user_said_do_not_run,
)


def should_execute_now(
    intent: str,
    workspace_count: int,
    risk: str,
    *,
    user_text: str = "",
) -> bool:
    """
    Hard gate: low risk, single workspace, dev-class intent, no opt-out / destructive phrasing.
    Kept in sync with :func:`should_auto_execute_dev` (which derives risk from text).
    """
    if risk != "low":
        return False
    if workspace_count != 1:
        return False
    if intent not in ("stuck_dev", "analysis"):
        return False
    t = (user_text or "").strip()
    if contains_destructive_language(t):
        return False
    if user_said_do_not_run(t):
        return False
    return True


def compute_execution_confidence(
    intent: str,
    user_text: str,
    *,
    memory_summary: str | None,
    workspace_count: int,
) -> Literal["high", "medium", "low"]:
    """
    Heuristic confidence for auto-execution (Phase 55). Does not replace policy gates;
    use for logging, UI, and future “confirm on medium” flows.
    """
    risk = assess_interaction_risk(user_text)
    if risk == "high":
        return "low"
    if workspace_count != 1:
        return "low"
    if intent not in ("stuck_dev", "analysis"):
        return "low"
    if risk == "medium":
        return "low"
    t = (user_text or "").strip()
    mem = (memory_summary or "").strip()
    if len(t) >= 24 and (mem and len(mem) > 24):
        return "high"
    if any(k in t.lower() for k in ("error", "fail", "traceback", "exception", "panic", "pytest", "npm test")):
        return "high"
    if len(t) < 16:
        return "medium"
    return "medium"


def should_auto_execute_dev(user_text: str, intent: str, *, workspace_count: int) -> bool:
    """
    True when a dev investigation mission should run automatically (single workspace,
    safe intent, low risk). Delegates to :func:`should_auto_execute_dev_turn`.
    """
    risk = assess_interaction_risk(user_text)
    return should_auto_execute_dev_turn(intent, risk, workspace_count, user_text)


def should_use_decisive_dev_tone(intent: str) -> bool:
    """Suppress generic coaching (next steps, question-back) for dev-analysis intents."""
    s = get_settings()
    if not getattr(s, "nexa_decisive_dev_chat", True):
        return False
    return intent in ("stuck_dev", "analysis")


def should_merge_phase50_assist(intent: str) -> bool:
    """Phase 50 appendix — skip when decisive dev tone would contradict action-first UX."""
    return not should_use_decisive_dev_tone(intent)


__all__ = [
    "compute_execution_confidence",
    "should_auto_execute_dev",
    "should_execute_now",
    "should_merge_phase50_assist",
    "should_use_decisive_dev_tone",
]
