"""CRUD, dispatch, and read helpers for agent organizations and assignments."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_team import AgentAssignment, AgentOrganization, AgentRoleAssignment
from app.services.agent_team.host_bridge import try_assignment_host_dispatch
from app.services.cursor_integration import try_cursor_dispatch
from app.services.agent_team.planner import DEFAULT_ORCHESTRATOR
from app.services.audit_service import audit
from app.services.custom_agents import (
    display_agent_handle,
    display_agent_handle_label,
    get_custom_agent,
    normalize_agent_key,
    run_custom_user_agent,
)

logger = logging.getLogger(__name__)

_ASSIGNMENT_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
_DEDUPE_WINDOW_MINUTES = 30


class DuplicateAssignmentError(Exception):
    """Raised when create_assignment would duplicate recent non-terminal work with the same title + agent."""

    def __init__(self, existing: AgentAssignment):
        self.existing = existing
        super().__init__(f"Duplicate of assignment #{existing.id}")


def _now() -> datetime:
    return datetime.utcnow()


def _normalize_assignment_title_key(title: str) -> str:
    return " ".join((title or "").lower().split())[:500]


def find_recent_duplicate_assignment(
    db: Session,
    *,
    user_id: str,
    assigned_to_handle: str,
    title: str,
    within_minutes: int = _DEDUPE_WINDOW_MINUTES,
) -> AgentAssignment | None:
    """Same user + agent + normalized title, created recently, still active."""
    uid = (user_id or "").strip()[:64]
    h = normalize_agent_key(assigned_to_handle)
    key = _normalize_assignment_title_key(title)
    if not key:
        return None
    since = _now() - timedelta(minutes=max(1, min(int(within_minutes), 24 * 60)))
    rows = list(
        db.scalars(
            select(AgentAssignment)
            .where(
                AgentAssignment.user_id == uid,
                AgentAssignment.assigned_to_handle == h,
                AgentAssignment.created_at >= since,
            )
            .order_by(AgentAssignment.created_at.desc())
            .limit(40)
        ).all()
    )
    for row in rows:
        if (row.status or "") in _ASSIGNMENT_TERMINAL_STATUSES:
            continue
        if _normalize_assignment_title_key(row.title) == key:
            return row
    return None


def get_or_create_default_organization(db: Session, user_id: str) -> AgentOrganization:
    uid = (user_id or "").strip()[:64]
    stmt = (
        select(AgentOrganization)
        .where(AgentOrganization.user_id == uid)
        .order_by(AgentOrganization.id.asc())
        .limit(1)
    )
    row = db.scalars(stmt).first()
    if row:
        return row
    org = AgentOrganization(
        user_id=uid,
        name="My agent team",
        description="Default Nexa agent organization",
        enabled=True,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    audit(
        db,
        event_type="agent_org.created",
        actor="nexa",
        user_id=uid,
        message=f"Created default agent organization #{org.id}",
        metadata={"organization_id": org.id},
    )
    return org


def create_agent_organization(
    db: Session,
    *,
    user_id: str,
    name: str,
    description: str | None = None,
) -> AgentOrganization:
    uid = (user_id or "").strip()[:64]
    org = AgentOrganization(
        user_id=uid,
        name=(name or "Team")[:200],
        description=(description or "")[:8000] or None,
        enabled=True,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    audit(
        db,
        event_type="agent_org.created",
        actor="nexa",
        user_id=uid,
        message=f"Created agent organization #{org.id} {org.name!r}",
        metadata={"organization_id": org.id},
    )
    return org


def assign_agent_to_org(
    db: Session,
    *,
    organization_id: int,
    agent_handle: str,
    role: str,
    skills: list[str] | None = None,
    reports_to_handle: str | None = None,
    responsibilities: list[str] | None = None,
) -> AgentRoleAssignment:
    h = normalize_agent_key(agent_handle)
    row = AgentRoleAssignment(
        organization_id=int(organization_id),
        agent_handle=h,
        role=(role or "")[:200],
        reports_to_handle=(reports_to_handle or None),
        skills_json=list(skills or []),
        responsibilities_json=list(responsibilities or []),
        priority="normal",
        enabled=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    org = db.get(AgentOrganization, organization_id)
    audit(
        db,
        event_type="agent_role.assigned",
        actor="nexa",
        user_id=(org.user_id if org else None),
        message=f"Role for @{h} in org #{organization_id}",
        metadata={
            "organization_id": organization_id,
            "agent_handle": h,
            "role_id": row.id,
        },
    )
    return row


def create_assignment(
    db: Session,
    *,
    user_id: str,
    assigned_to_handle: str,
    title: str,
    description: str,
    organization_id: int | None = None,
    assigned_by_handle: str = "orchestrator",
    priority: str = "normal",
    input_json: dict[str, Any] | None = None,
    channel: str = "web",
    channel_user_id: str | None = None,
    web_session_id: str | None = None,
    parent_assignment_id: int | None = None,
    skip_duplicate_check: bool = False,
    initial_status: str | None = None,
) -> AgentAssignment:
    uid = (user_id or "").strip()[:64]
    h = normalize_agent_key(assigned_to_handle)
    if not skip_duplicate_check:
        dup = find_recent_duplicate_assignment(db, user_id=uid, assigned_to_handle=h, title=(title or ""))
        if dup is not None:
            raise DuplicateAssignmentError(dup)
    st = (initial_status or "queued").strip() or "queued"
    if st not in (
        "queued",
        "assigned",
        "waiting_worker",
        "waiting_approval",
        "running",
        "completed",
        "failed",
        "cancelled",
    ):
        st = "queued"
    row = AgentAssignment(
        user_id=uid,
        organization_id=organization_id,
        parent_assignment_id=parent_assignment_id,
        assigned_to_handle=h,
        assigned_by_handle=(assigned_by_handle or "orchestrator")[:64],
        title=(title or "")[:500],
        description=(description or "")[:20_000],
        status=st[:32],
        priority=(priority or "normal")[:32],
        input_json=dict(input_json or {}),
        channel=(channel or "web")[:32],
        channel_user_id=(channel_user_id or None),
        web_session_id=(web_session_id or None),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(
        db,
        event_type="agent_assignment.created",
        actor="nexa",
        user_id=uid,
        message=f"Assignment #{row.id} → @{h}: {title[:120]}",
        metadata={
            "assignment_id": row.id,
            "organization_id": organization_id,
            "assigned_to_handle": h,
            "assigned_by_handle": row.assigned_by_handle,
            "channel": channel,
        },
    )
    return row


def _assignment_audit(
    db: Session,
    *,
    event_type: str,
    user_id: str | None,
    message: str,
    assignment_id: int,
    extra: dict[str, Any] | None = None,
) -> None:
    md = {"assignment_id": assignment_id}
    if extra:
        md.update(extra)
    audit(
        db,
        event_type=event_type,
        actor="nexa",
        user_id=user_id,
        message=message[:4000],
        metadata=md,
    )


def dispatch_assignment(db: Session, *, assignment_id: int, user_id: str) -> dict[str, Any]:
    """Run queued/assigned work for a custom agent; finalize status + output."""
    uid = (user_id or "").strip()[:64]
    row = db.get(AgentAssignment, int(assignment_id))
    if not row or row.user_id != uid:
        return {"ok": False, "error": "Assignment not found."}
    if row.status in ("completed", "failed", "cancelled"):
        return {"ok": False, "error": f"Assignment is already {row.status}."}
    if row.status == "running":
        return {
            "ok": False,
            "error": "Assignment is already running.",
            "assignment_id": row.id,
        }
    if row.status == "waiting_approval":
        return {
            "ok": False,
            "error": "This assignment is waiting for access approval. Approve the permission request first.",
            "assignment_id": row.id,
        }
    if row.status not in ("queued", "assigned", "waiting_worker"):
        return {"ok": False, "error": f"Assignment not dispatchable from status {row.status}."}

    # Host tools / permission gate (runs before LLM-only custom agent path).
    host_res = try_assignment_host_dispatch(db, row=row, uid=uid)
    if host_res is not None:
        if not host_res.get("ok") and not host_res.get("waiting_approval"):
            db.refresh(row)
            row.status = "failed"
            row.completed_at = _now()
            row.error = (host_res.get("error") or "Assignment failed.")[:8000]
            db.add(row)
            db.commit()
            _assignment_audit(
                db,
                event_type="agent_assignment.failed",
                user_id=uid,
                message=f"Assignment #{row.id} failed (host phase)",
                assignment_id=row.id,
            )
        return host_res

    cursor_res = try_cursor_dispatch(db, row=row, uid=uid)
    if cursor_res is not None:
        return cursor_res

    handle = row.assigned_to_handle
    if handle == normalize_agent_key(DEFAULT_ORCHESTRATOR):
        msg = (
            "I could not auto-route this goal to a specialist from keywords alone. "
            "Name the agents or say e.g. **assign @research-analyst to summarize …** "
            "after you have created those custom agents."
        )
        row.status = "completed"
        row.completed_at = _now()
        row.output_json = {"text": msg, "kind": "orchestrator_clarify"}
        row.error = None
        db.add(row)
        db.commit()
        _assignment_audit(
            db,
            event_type="agent_assignment.completed",
            user_id=uid,
            message=f"Assignment #{row.id} completed (clarification)",
            assignment_id=row.id,
        )
        return {"ok": True, "assignment_id": row.id, "output": row.output_json}

    agent = get_custom_agent(db, uid, handle)
    if not agent:
        ij = row.input_json if isinstance(row.input_json, dict) else {}
        spawn_missing = bool(str(ij.get("spawn_group_id") or "").strip())
        if spawn_missing:
            row.status = "waiting_worker"
            row.completed_at = None
            row.error = None
            row.output_json = {
                "kind": "waiting_worker",
                "text": (
                    f"No custom agent {display_agent_handle(handle)} yet. "
                    f"Create it, then dispatch assignment #{row.id} again."
                )[:8000],
            }
            db.add(row)
            db.commit()
            _assignment_audit(
                db,
                event_type="agent_assignment.waiting_worker",
                user_id=uid,
                message=f"Assignment #{row.id} waiting for custom agent",
                assignment_id=row.id,
            )
            return {
                "ok": False,
                "error": row.output_json.get("text") if isinstance(row.output_json, dict) else None,
                "assignment_id": row.id,
                "waiting_worker": True,
            }
        row.status = "failed"
        row.completed_at = _now()
        row.error = (
            f"No custom agent {display_agent_handle(handle)} for your account. "
            "Create it first, then retry."
        )
        db.add(row)
        db.commit()
        _assignment_audit(
            db,
            event_type="agent_assignment.failed",
            user_id=uid,
            message=f"Assignment #{row.id} failed: missing agent",
            assignment_id=row.id,
        )
        return {"ok": False, "error": row.error, "assignment_id": row.id}

    if row.status in ("queued", "assigned", "waiting_worker"):
        row.status = "running"
        row.started_at = _now()
        db.add(row)
        db.commit()
        db.refresh(row)
        _assignment_audit(
            db,
            event_type="agent_assignment.dispatched",
            user_id=uid,
            message=f"Dispatched assignment #{row.id}",
            assignment_id=row.id,
            extra={"assigned_to": row.assigned_to_handle},
        )

    body = (row.input_json or {}).get("user_message") or row.description or ""
    try:
        text_out = run_custom_user_agent(
            db, uid, agent, body, source="agent_assignment"
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("dispatch_assignment agent run: %s", exc)
        row.status = "failed"
        row.completed_at = _now()
        row.error = str(exc)[:8000]
        db.add(row)
        db.commit()
        _assignment_audit(
            db,
            event_type="agent_assignment.failed",
            user_id=uid,
            message=f"Assignment #{row.id} failed",
            assignment_id=row.id,
            extra={"error": row.error[:500]},
        )
        return {"ok": False, "error": row.error, "assignment_id": row.id}

    row.status = "completed"
    row.completed_at = _now()
    row.output_json = {"text": text_out}
    row.error = None
    db.add(row)
    db.commit()
    _assignment_audit(
        db,
        event_type="agent_assignment.completed",
        user_id=uid,
        message=f"Assignment #{row.id} completed",
        assignment_id=row.id,
    )
    return {"ok": True, "assignment_id": row.id, "output": row.output_json}


def cancel_assignment(db: Session, *, assignment_id: int, user_id: str) -> dict[str, Any]:
    uid = (user_id or "").strip()[:64]
    row = db.get(AgentAssignment, int(assignment_id))
    if not row or row.user_id != uid:
        return {"ok": False, "error": "Assignment not found."}
    if row.status in ("completed", "failed", "cancelled"):
        return {"ok": False, "error": f"Cannot cancel from status {row.status}."}
    row.status = "cancelled"
    row.completed_at = _now()
    db.add(row)
    db.commit()
    _assignment_audit(
        db,
        event_type="agent_assignment.cancelled",
        user_id=uid,
        message=f"Cancelled assignment #{row.id}",
        assignment_id=row.id,
    )
    return {"ok": True, "assignment_id": row.id}


def get_assignment_status(db: Session, *, assignment_id: int, user_id: str) -> dict[str, Any] | None:
    uid = (user_id or "").strip()[:64]
    row = db.get(AgentAssignment, int(assignment_id))
    if not row or row.user_id != uid:
        return None
    return assignment_to_dict(row)


def assignment_to_dict(row: AgentAssignment) -> dict[str, Any]:
    ah = row.assigned_to_handle or ""
    ab = row.assigned_by_handle or ""
    out = dict(row.output_json or {}) if row.output_json else {}
    cur = out.get("cursor") if isinstance(out.get("cursor"), dict) else {}
    ij = dict(row.input_json or {})
    sg_raw = ij.get("spawn_group_id")
    spawn_gid = (
        str(sg_raw).strip()[:120] if isinstance(sg_raw, str) and str(sg_raw).strip() else None
    )
    base = {
        "id": row.id,
        "user_id": row.user_id,
        "organization_id": row.organization_id,
        "parent_assignment_id": row.parent_assignment_id,
        "assigned_to_handle": ah,
        "assigned_to_handle_display": display_agent_handle_label(ah),
        "assigned_by_handle": ab,
        "assigned_by_handle_display": display_agent_handle_label(ab),
        "title": row.title,
        "description": row.description,
        "status": row.status,
        "spawn_group_id": spawn_gid,
        "priority": row.priority,
        "input_json": dict(row.input_json or {}),
        "output_json": dict(row.output_json or {}) if row.output_json else None,
        "error": row.error,
        "channel": row.channel,
        "web_session_id": row.web_session_id,
        "started_at": row.started_at.isoformat() + "Z" if row.started_at else None,
        "completed_at": row.completed_at.isoformat() + "Z" if row.completed_at else None,
        "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
        "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else None,
    }
    base["cursor_run_id"] = cur.get("cursor_run_id")
    base["cursor_status"] = cur.get("cursor_status")
    base["cursor_repo"] = cur.get("cursor_repo")
    base["cursor_branch"] = cur.get("cursor_branch")
    base["cursor_cost_estimate"] = cur.get("cursor_cost_estimate")
    return base


def list_assignments_for_user(
    db: Session,
    user_id: str,
    *,
    limit: int = 40,
    web_session_id: str | None = None,
) -> list[dict[str, Any]]:
    uid = (user_id or "").strip()[:64]
    stmt = select(AgentAssignment).where(AgentAssignment.user_id == uid)
    if web_session_id:
        w = (web_session_id or "").strip()[:64]
        stmt = stmt.where(AgentAssignment.web_session_id == w)
    stmt = stmt.order_by(AgentAssignment.id.desc()).limit(max(1, min(limit, 200)))
    rows = list(db.scalars(stmt).all())
    return [assignment_to_dict(r) for r in rows]


def summarize_assignment_progress(db: Session, *, user_id: str) -> list[dict[str, Any]]:
    """Lightweight rows for Mission Control + chat."""
    return list_assignments_for_user(db, user_id, limit=25)
