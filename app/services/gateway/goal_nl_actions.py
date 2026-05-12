# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Gateway NL: autonomous goal planning (owner-only; gated by Settings)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.gateway.context import GatewayContext
from app.services.gateway.early_nl_host_actions import _workspace_root_for_nl
from app.services.execution_planner import acquire_plan_slot, release_plan_slot
from app.services.goal_orchestrator import GoalOrchestrator, format_goal_result, parse_goal_intent
from app.services.user_capabilities import is_privileged_owner_for_web_mutations


def try_goal_planning_gateway_turn(
    gctx: GatewayContext,
    raw_message: str,
    db: Session,
) -> dict[str, Any] | None:
    """
    Deterministic goal execution after ``early_nl`` shortcuts.

    Requires ``nexa_autonomous_goal_planning``, privileged owner, and ``nexa_auto_approve_owner``.
    """
    _ = db
    if not bool(getattr(get_settings(), "nexa_autonomous_goal_planning", False)):
        return None
    if not bool(getattr(get_settings(), "nexa_auto_approve_owner", True)):
        return None
    uid = (gctx.user_id or "").strip()
    raw = (raw_message or "").strip()
    if not raw or not uid:
        return None
    if not is_privileged_owner_for_web_mutations(db, uid):
        return None
    parsed = parse_goal_intent(raw)
    if not parsed:
        return None
    orch = GoalOrchestrator()
    goal = orch.plan_sync(parsed, raw)
    root = _workspace_root_for_nl()

    max_p = int(getattr(get_settings(), "nexa_max_concurrent_plans", 3) or 3)
    if not acquire_plan_slot(uid, max_p):
        return {
            "mode": "chat",
            "text": (
                f"**Too many concurrent goal plans** for this user (max {max_p}). "
                "Finish or wait for one to complete, then try again."
            ),
            "intent": "goal_throttled",
        }
    try:
        payload = orch.execute_goal_sync(goal, workspace_root=root, owner_user_id=uid)
    finally:
        release_plan_slot(uid)
    text = format_goal_result(payload, goal)
    return {
        "mode": "chat",
        "text": text,
        "intent": "goal_completed",
        "goal_orchestration": True,
        "goal_id": payload.get("goal_id"),
        "goal_ok": payload.get("ok"),
    }


__all__ = ["try_goal_planning_gateway_turn"]
