"""
Phase 73 — agent health + manual self-heal triggers (Genesis Loop).

* ``GET /api/v1/agent/health/{agent_id}`` — current status, last_active, recent
  failure rollup, recovery metadata. Open to any web user with the agent in
  their orchestration scope (same gate the rest of ``/agents/*`` uses).
* ``POST /api/v1/agent/health/{agent_id}/diagnose`` — runs the heuristic
  diagnosis (and the optional cost-aware LLM summary) and returns the result.
  Owner-only — diagnosis is cheap but it can call the LLM.
* ``POST /api/v1/agent/health/{agent_id}/recover`` — runs diagnose + recovery
  and returns both the diagnosis and the recovery result. Owner-only — this
  mutates agent state.

Agent scoping uses the existing ``_api_orchestration_scopes`` /
``_ensure_agent_in_scopes`` pair from :mod:`app.api.routes.agent_spawn` so a
user can only see their own agents (or all of them when they are the owner via
the orchestration scope rules).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes.agent_spawn import (
    _api_orchestration_scopes,
    _ensure_agent_in_scopes,
)
from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.services.agent.activity_tracker import get_activity_tracker
from app.services.agent.recovery import get_recovery_handler
from app.services.agent.self_diagnosis import get_self_diagnosis
from app.services.user_capabilities import (
    get_telegram_role_for_app_user,
    is_owner_role,
)

router = APIRouter(prefix="/agent/health", tags=["agent-health"])


def _ensure_enabled() -> None:
    s = get_settings()
    if not bool(getattr(s, "nexa_self_healing_enabled", False)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Self-healing is disabled (NEXA_SELF_HEALING_ENABLED=false).",
        )


def _require_owner(db: Session, app_user_id: str) -> None:
    role = get_telegram_role_for_app_user(db, app_user_id)
    if not is_owner_role(role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Manual diagnose / recover require the Telegram-linked owner. "
                "Auto-recovery still runs in the supervisor for any failing agent."
            ),
        )


def _build_health_payload(agent: Any) -> dict[str, Any]:
    tracker = get_activity_tracker()
    s = get_settings()
    window_min = max(1, int(getattr(s, "nexa_agent_failure_window_minutes", 60) or 60))
    window_hours = max(1, (window_min // 60) + (1 if window_min % 60 else 0))

    history_window = tracker.get_agent_history(
        agent.id, hours=window_hours, limit=100
    )
    history_24h = tracker.get_agent_history(agent.id, hours=24, limit=100)

    md = dict(agent.metadata or {})
    failures_window = [h for h in history_window if not h.get("success")]
    failures_24h = [h for h in history_24h if not h.get("success")]

    return {
        "agent": {
            "id": agent.id,
            "name": agent.name,
            "domain": agent.domain,
            "status": agent.status.value,
            "last_active": getattr(agent, "last_active", None),
        },
        "self_healing": {
            "enabled": bool(getattr(s, "nexa_self_healing_enabled", False)),
            "failure_threshold": int(
                getattr(s, "nexa_agent_failure_threshold", 3) or 3
            ),
            "failure_window_minutes": window_min,
            "max_recovery_attempts": int(
                getattr(s, "nexa_agent_max_auto_recovery_attempts", 3) or 3
            ),
            "recovery_attempts": int(md.get("recovery_attempts", 0) or 0),
            "last_recovery_strategy": md.get("last_recovery_strategy"),
            "last_recovery_at": md.get("last_recovery_at"),
            "fallback_llm": md.get("fallback_llm"),
        },
        "failures": {
            "in_window_count": len(failures_window),
            "in_24h_count": len(failures_24h),
            "recent": [
                {
                    "action_type": h.get("action_type"),
                    "error": h.get("error"),
                    "created_at": h.get("created_at"),
                }
                for h in failures_24h[:10]
            ],
        },
    }


@router.get("/{agent_id}")
def get_agent_health(
    agent_id: str,
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _ensure_enabled()
    scopes = _api_orchestration_scopes(app_user_id)
    _registry, agent = _ensure_agent_in_scopes(agent_id, scopes)
    return {"ok": True, **_build_health_payload(agent)}


@router.post("/{agent_id}/diagnose")
def diagnose_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _ensure_enabled()
    _require_owner(db, app_user_id)
    scopes = _api_orchestration_scopes(app_user_id)
    _registry, agent = _ensure_agent_in_scopes(agent_id, scopes)
    diagnosis = get_self_diagnosis().diagnose(agent)
    return {"ok": True, "agent_id": agent.id, "diagnosis": diagnosis.to_dict()}


@router.post("/{agent_id}/recover")
def recover_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _ensure_enabled()
    _require_owner(db, app_user_id)
    scopes = _api_orchestration_scopes(app_user_id)
    _registry, agent = _ensure_agent_in_scopes(agent_id, scopes)
    diagnosis = get_self_diagnosis().diagnose(agent)
    result = get_recovery_handler().attempt(agent, diagnosis)
    return {
        "ok": True,
        "agent_id": agent.id,
        "diagnosis": diagnosis.to_dict(),
        "recovery": result.to_dict(),
    }


__all__ = ["router"]
