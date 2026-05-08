"""
Phase 70 — Mission Control "Pending Approvals" panel API.

Surfaces existing :class:`~app.models.agent_job.AgentJob` rows that are flagged
``awaiting_approval=True`` (Phase 38 approval gate) so the web UI can list and
approve / deny them. Approve / deny still flows through the existing
``POST /api/v1/jobs/{id}/decision`` endpoint (this module is read-only by design
to avoid splitting the source of truth with the legacy Telegram approval queue).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import get_current_user_id
from app.models.agent_job import AgentJob
from app.services.execution_policy import assess_interaction_risk

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _job_to_pending_row(job: AgentJob) -> dict[str, Any]:
    """Return the minimal payload the web panel needs to render one approval card."""
    payload = job.payload_json or {}
    payload_safe = payload if isinstance(payload, dict) else {}
    host_action = (payload_safe.get("host_action") or payload_safe.get("action") or "").strip().lower() or None
    target = (
        payload_safe.get("provider")
        or payload_safe.get("target")
        or payload_safe.get("repo")
        or payload_safe.get("workspace")
        or None
    )
    description_source = (job.instruction or job.title or "").strip()
    description = description_source[:500] if description_source else ""

    return {
        "id": job.id,
        "title": job.title or "Pending action",
        "description": description,
        "kind": job.kind,
        "worker_type": job.worker_type,
        "command_type": job.command_type,
        "host_action": host_action,
        "target": target,
        "risk_level": job.risk_level,
        "status": job.status,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "approval_decision": job.approval_decision,
        "approval_context": job.approval_context_json,
        "payload_preview": _payload_preview(payload_safe),
    }


def _payload_preview(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip large / sensitive fields before sending to the browser."""
    if not isinstance(payload, dict):
        return {}
    preview: dict[str, Any] = {}
    for key in (
        "host_action",
        "action",
        "command",
        "argv",
        "ref",
        "remote",
        "branch",
        "service",
        "environment",
        "cwd_relative",
        "files",
        "repo",
        "workspace",
        "provider",
        "skill",
        "actions",
    ):
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(value, str) and len(value) > 500:
            preview[key] = value[:497] + "…"
        elif isinstance(value, (list, dict)):
            try:
                import json

                serialized = json.dumps(value, default=str)
            except (TypeError, ValueError):
                serialized = str(value)
            if len(serialized) > 1500:
                preview[key] = serialized[:1497] + "…"
            else:
                preview[key] = value
        else:
            preview[key] = value
    return preview


@router.get("/pending")
def list_pending_approvals(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    limit: int = 50,
) -> dict[str, Any]:
    """
    Return ``agent_jobs`` rows where ``awaiting_approval=True`` for the caller.

    The companion approve / deny endpoints already exist at
    ``POST /api/v1/jobs/{id}/decision`` (payload ``{"decision": "approved" | "denied"}``);
    this endpoint deliberately does **not** mutate state.
    """
    settings = get_settings()
    if not bool(getattr(settings, "nexa_approvals_panel_enabled", True)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Approvals panel disabled (set NEXA_APPROVALS_PANEL_ENABLED=1 to enable).",
        )

    safe_limit = max(1, min(int(limit or 0) or 50, 200))
    stmt = (
        select(AgentJob)
        .where(AgentJob.user_id == user_id)
        .where(AgentJob.awaiting_approval.is_(True))
        .order_by(AgentJob.created_at.desc())
        .limit(safe_limit)
    )
    rows = list(db.scalars(stmt).all())
    return {
        "approvals": [_job_to_pending_row(job) for job in rows],
        "count": len(rows),
        "limit": safe_limit,
    }


@router.get("/risk-preview")
def preview_action_risk(text: str = "") -> dict[str, Any]:
    """
    Lightweight helper so the UI / agents can ask "what risk tier would this be?"
    without having to wire up the full host_executor pipeline. Wraps
    :func:`app.services.execution_policy.assess_interaction_risk`.
    """
    tier = assess_interaction_risk(text)
    return {"risk": tier, "text_preview": (text or "")[:200]}
