"""Phase 45B — gates autonomous execution against budgets and privacy posture."""

from __future__ import annotations

from app.core.config import get_settings
from app.models.autonomy import NexaAutonomousTask
from app.services.token_economy.budget import check_budget
from app.services.user_settings.service import effective_privacy_mode


def should_execute(
    db,
    user_id: str,
    *,
    task_row: NexaAutonomousTask | None = None,
    token_estimate: int = 1800,
    provider: str = "anthropic",
) -> tuple[bool, str]:
    """
    Return (allowed, reason). When ``allowed`` is False, executor skips the task for this cycle.

    ``task_row`` is optional — reserved for per-task caps later (Phase 45+).
    """
    _ = task_row
    if not getattr(get_settings(), "nexa_autonomous_mode", False):
        return False, "autonomous_mode_off"
    if not getattr(get_settings(), "nexa_autonomy_execution_enabled", True):
        return False, "execution_disabled"

    mode = effective_privacy_mode(db, user_id)
    if str(getattr(mode, "value", mode)).lower() in ("strict", "paranoid"):
        return False, "privacy_mode_strict"

    if getattr(get_settings(), "nexa_strict_privacy_mode", False):
        return False, "global_strict_privacy"

    block = check_budget(db, user_id, token_estimate=int(token_estimate), provider=provider)
    if block:
        return False, f"budget:{block}"

    return True, "ok"


__all__ = ["should_execute"]
