"""Phase 55 — centralized policy for when Nexa should execute vs stay in suggestion mode."""

from __future__ import annotations

from app.core.config import get_settings
from app.services.execution_policy import assess_interaction_risk, should_auto_execute_dev_turn


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
    "should_auto_execute_dev",
    "should_merge_phase50_assist",
    "should_use_decisive_dev_tone",
]
