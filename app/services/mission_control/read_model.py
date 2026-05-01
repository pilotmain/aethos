"""Aggregate Mission Control dashboard data from existing Nexa services (no duplicate logic)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.access_permission import AccessPermission
from app.models.agent_team import AgentOrganization, AgentRoleAssignment
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.access_permissions import STATUS_PENDING
from app.services.agent_job_service import TERMINAL_JOB_STATUSES, AgentJobService
from app.services.channel_gateway.governance import merge_channel_status_governance
from app.services.channel_gateway.status import build_channel_status_list
from app.services.mission_control.cleanup_actions import assignment_hidden_mc, job_dismissed_mc
from app.services.mission_control.scoring import score_mission_item
from app.services.mission_control.ui_state import dismissed_attention_ids
from app.services.trust_audit_constants import NETWORK_EXTERNAL_SEND_BLOCKED
from app.services.agent_team.service import list_assignments_for_user
from app.services.custom_agents import display_agent_handle_label
from app.services.trust_audit_read_model import audit_row_to_event, query_trust_activity, summarize_trust_activity

_GATEWAY_OUTBOUND_FAILED = "gateway.outbound_failed"


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat() + "Z"


def _perm_channel(p: AccessPermission) -> str | None:
    md = dict(p.metadata_json or {})
    c = md.get("channel")
    if c:
        return str(c).strip().lower()[:32]
    return "web"


def _query_gateway_failures(db: Session, user_id: str, since: datetime, *, limit: int = 40) -> list[AuditLog]:
    stmt = (
        select(AuditLog)
        .where(
            AuditLog.user_id == user_id,
            AuditLog.event_type == _GATEWAY_OUTBOUND_FAILED,
            AuditLog.created_at >= since,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def _event_bucket_channel(ev: dict[str, Any]) -> str:
    ch = ev.get("channel")
    if ch and str(ch).strip():
        return str(ch).strip().lower()[:32]
    return "system"


def _orchestration_snapshot(db: Session, user_id: str) -> dict[str, Any]:
    uid = (user_id or "").strip()[:64]
    org = db.scalars(
        select(AgentOrganization)
        .where(AgentOrganization.user_id == uid)
        .order_by(AgentOrganization.id.asc())
        .limit(1)
    ).first()
    roles_out: list[dict[str, Any]] = []
    org_out: dict[str, Any] | None = None
    if org:
        org_out = {"id": org.id, "name": org.name, "enabled": bool(org.enabled)}
        rrows = list(
            db.scalars(
                select(AgentRoleAssignment)
                .where(AgentRoleAssignment.organization_id == org.id)
                .order_by(AgentRoleAssignment.id.asc())
            ).all()
        )
        roles_out = [
            {
                "agent_handle": r.agent_handle,
                "agent_handle_display": display_agent_handle_label(r.agent_handle),
                "role": r.role,
                "reports_to_handle": r.reports_to_handle,
                "reports_to_handle_display": display_agent_handle_label(r.reports_to_handle)
                if r.reports_to_handle
                else None,
                "enabled": r.enabled,
            }
            for r in rrows
        ]
    assigns_raw = list_assignments_for_user(db, uid, limit=30)
    assigns = [
        a
        for a in assigns_raw
        if not assignment_hidden_mc(a)
        and str(a.get("status") or "").strip().lower() != "cancelled"
    ]
    return {"organization": org_out, "roles": roles_out, "assignments": assigns}


def _attention_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    ts = item.get("created_at") or ""
    return (-int(item.get("score") or 0), ts)


def build_mission_control_summary(db: Session, user_id: str, *, hours: int = 24) -> dict[str, Any]:
    """
    Build Mission Control JSON for ``GET /api/v1/mission-control/summary``.

    Aggregates trust activity, jobs, pending permissions, channel status, and gateway failures.
    """
    uid = (user_id or "").strip()[:64]
    dismissed_mc = dismissed_attention_ids(uid)
    window_h = float(max(1, min(int(hours), 168)))
    since = datetime.utcnow() - timedelta(hours=window_h)

    trust_summary = summarize_trust_activity(db, uid, window_hours=window_h, recent_limit=100)
    trust_events = query_trust_activity(db, uid, since=since, limit=200)
    gateway_rows = _query_gateway_failures(db, uid, since, limit=40)
    gateway_events = [audit_row_to_event(r) for r in gateway_rows]

    job_svc = AgentJobService()
    jobs_raw = job_svc.list_jobs(db, uid, limit=80)
    jobs = [j for j in jobs_raw if not job_dismissed_mc(j)]

    pend_stmt = (
        select(AccessPermission)
        .where(AccessPermission.owner_user_id == uid, AccessPermission.status == STATUS_PENDING)
        .order_by(AccessPermission.id.desc())
        .limit(40)
    )
    pending_perms = list(db.scalars(pend_stmt).all())

    urow = db.get(User, uid)
    oid = ((urow.organization_id if urow else None) or "").strip() or None
    if not oid:
        oid = (get_settings().nexa_default_organization_id or "").strip() or None
    ch_rows = merge_channel_status_governance(db, build_channel_status_list(), organization_id=oid)

    # --- Overview counts ---
    non_terminal = [j for j in jobs if (getattr(j, "status", None) or "") not in TERMINAL_JOB_STATUSES]
    active_jobs_ct = len(non_terminal)

    blocked_actions_ct = int(trust_summary.network_send_blocked + trust_summary.host_executor_blocks)
    high_risk_ct = int(trust_summary.sensitive_egress_warnings + trust_summary.enforcement_paths)

    active_channels_ct = sum(
        1
        for r in ch_rows
        if bool(r.get("configured")) and bool(r.get("enabled")) and (r.get("health") or "") != "missing_config"
    )

    # Recent executions ≈ permission uses in window (real audit-backed metric).
    recent_exec_ct = int(trust_summary.permission_uses)

    pending_visible_ct = sum(1 for p in pending_perms if f"perm-{p.id}" not in dismissed_mc)
    overview = {
        "active_jobs": active_jobs_ct,
        "pending_approvals": pending_visible_ct,
        "blocked_actions": blocked_actions_ct,
        "high_risk_events": high_risk_ct,
        "active_channels": active_channels_ct,
        "recent_executions": recent_exec_ct,
    }

    # --- Channel activity counts (trust events + gateway failures in window) ---
    counts_by_channel: dict[str, int] = {}
    for ev in trust_events + gateway_events:
        key = _event_bucket_channel(ev)
        counts_by_channel[key] = counts_by_channel.get(key, 0) + 1

    channels_section: list[dict[str, Any]] = []
    for r in ch_rows:
        key = str(r.get("channel") or "")
        n = int(counts_by_channel.get(key, 0))
        channels_section.append({**dict(r), "recent_event_count": n})
    # System bucket (events without channel lineage)
    sys_n = int(counts_by_channel.get("system", 0))
    channels_section.append(
        {
            "channel": "system",
            "label": "System",
            "available": True,
            "configured": True,
            "enabled": True,
            "health": "ok",
            "recent_event_count": sys_n,
            "missing": [],
            "notes": ["Trust events without channel metadata"],
        }
    )

    # --- Attention queue ---
    attention: list[dict[str, Any]] = []

    for p in pending_perms:
        pid = f"perm-{p.id}"
        if pid in dismissed_mc:
            continue
        item = {
            "id": pid,
            "type": "pending_approval",
            "title": f"Approval required: {p.scope}",
            "description": (p.target or "")[:500],
            "status": p.status,
            "risk_level": p.risk_level,
            "channel": _perm_channel(p),
            "score": score_mission_item({"type": "pending_approval"}),
            "created_at": _iso(p.created_at),
            "permission_id": p.id,
            "job_id": None,
        }
        attention.append(item)

    for ev in trust_events:
        st = ev.get("status") or ""
        et = str(ev.get("event_type") or "")
        if st == "blocked":
            base_type = "blocked_high_risk"
            if et == NETWORK_EXTERNAL_SEND_BLOCKED:
                dest = ev.get("destination")
                title = f"Blocked external send ({dest})" if dest else "Blocked external send"
            else:
                title = (ev.get("message") or et)[:120]
            attention.append(
                {
                    "id": f"trust-{ev.get('id')}",
                    "type": base_type,
                    "title": title[:200],
                    "description": (ev.get("message") or "")[:400],
                    "status": st,
                    "risk_level": None,
                    "channel": _event_bucket_channel(ev),
                    "score": score_mission_item({"type": "blocked_high_risk"}),
                    "created_at": ev.get("created_at"),
                    "permission_id": None,
                    "job_id": ev.get("job_id"),
                }
            )
        elif st == "warning":
            attention.append(
                {
                    "id": f"trust-{ev.get('id')}",
                    "type": "sensitive_warning",
                    "title": (ev.get("event_type") or "Sensitive warning")[:120],
                    "description": (ev.get("message") or "")[:400],
                    "status": st,
                    "risk_level": str(ev.get("sensitivity_level") or ""),
                    "channel": _event_bucket_channel(ev),
                    "score": score_mission_item({"type": "sensitive_warning"}),
                    "created_at": ev.get("created_at"),
                    "permission_id": None,
                    "job_id": ev.get("job_id"),
                }
            )

    for ev in gateway_events:
        attention.append(
            {
                "id": f"gw-{ev.get('id')}",
                "type": "gateway_outbound_failed",
                "title": "Outbound delivery failed",
                "description": (ev.get("message") or "")[:400],
                "status": "failed",
                "risk_level": None,
                "channel": str(ev.get("channel") or _event_bucket_channel(ev)),
                "score": score_mission_item({"type": "gateway_outbound_failed"}),
                "created_at": ev.get("created_at"),
                "permission_id": None,
                "job_id": None,
            }
        )

    for j in jobs:
        st = (j.status or "").lower()
        if st == "failed":
            attention.append(
                {
                    "id": f"job-{j.id}",
                    "type": "failed_job",
                    "title": f"Job failed: {j.title[:120]}",
                    "description": ((j.error_message or j.instruction or "") or "")[:400],
                    "status": j.status,
                    "risk_level": j.risk_level,
                    "channel": (j.source or "web").lower(),
                    "score": score_mission_item({"type": "failed_job"}),
                    "created_at": _iso(j.updated_at or j.completed_at or j.created_at),
                    "permission_id": None,
                    "job_id": j.id,
                }
            )

    RUNNINGISH = frozenset(
        {
            "queued",
            "needs_approval",
            "waiting_approval",
            "agent_running",
            "waiting_for_cursor",
            "changes_ready",
            "ready_for_review",
            "needs_commit_approval",
            "needs_risk_approval",
            "approved_to_commit",
        }
    )
    for j in jobs:
        if (j.status or "") in RUNNINGISH:
            attention.append(
                {
                    "id": f"job-run-{j.id}",
                    "type": "running_job",
                    "title": f"Job running: {j.title[:120]}",
                    "description": (j.instruction or "")[:300],
                    "status": j.status,
                    "risk_level": j.risk_level,
                    "channel": (j.source or "web").lower(),
                    "score": score_mission_item({"type": "running_job"}),
                    "created_at": _iso(j.updated_at or j.started_at or j.created_at),
                    "permission_id": None,
                    "job_id": j.id,
                }
            )

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for it in sorted(attention, key=_attention_sort_key):
        iid = str(it.get("id") or "")
        if iid and iid not in seen:
            seen.add(iid)
            deduped.append(it)
    attention_out = [
        it for it in deduped[:50] if str(it.get("id") or "") not in dismissed_mc
    ]

    # --- Active work (non-terminal jobs first) ---
    non_terminal.sort(key=lambda j: j.updated_at or j.created_at, reverse=True)
    active_work: list[dict[str, Any]] = []
    for j in non_terminal[:20]:
        active_work.append(
            {
                "id": f"job-{j.id}",
                "type": "active_job",
                "title": j.title[:200],
                "description": (j.instruction or "")[:400],
                "status": j.status,
                "risk_level": j.risk_level,
                "channel": (j.source or "web").lower(),
                "score": score_mission_item({"type": "active_job"}),
                "created_at": _iso(j.updated_at or j.created_at),
                "permission_id": None,
                "job_id": j.id,
                "agent": j.worker_type,
                "started_at": _iso(j.started_at),
                "updated_at": _iso(j.updated_at),
            }
        )

    # --- Pending approvals (same rows as attention permissions; richer for UI) ---
    pending_out: list[dict[str, Any]] = []
    for p in pending_perms:
        pid = f"perm-{p.id}"
        if pid in dismissed_mc:
            continue
        pending_out.append(
            {
                "id": pid,
                "type": "pending_approval",
                "title": f"{p.scope}",
                "description": (p.reason or p.target or "")[:500],
                "status": p.status,
                "risk_level": p.risk_level,
                "channel": _perm_channel(p),
                "score": score_mission_item({"type": "pending_approval"}),
                "created_at": _iso(p.created_at),
                "permission_id": p.id,
                "job_id": None,
                "scope": p.scope,
                "target": p.target,
                "reason": p.reason,
            }
        )

    risk_summary = {
        "window_hours": trust_summary.window_hours,
        "counts": {
            "permission_uses": trust_summary.permission_uses,
            "network_external_send_allowed": trust_summary.network_send_allowed,
            "network_external_send_blocked": trust_summary.network_send_blocked,
            "sensitive_egress_warnings": trust_summary.sensitive_egress_warnings,
            "host_executor_blocks": trust_summary.host_executor_blocks,
            "safety_enforcement_paths": trust_summary.enforcement_paths,
        },
    }

    recommendations = _build_recommendations(
        overview=overview,
        pending_perms=pending_visible_ct,
        ch_rows=ch_rows,
        trust_blocked=int(trust_summary.network_send_blocked),
        failed_jobs=len([j for j in jobs if (j.status or "") == "failed"]),
        gateway_failures=len(gateway_rows),
    )

    quiet = (
        overview["active_jobs"] == 0
        and overview["pending_approvals"] == 0
        and overview["blocked_actions"] == 0
        and overview["high_risk_events"] == 0
        and len(attention_out) == 0
    )

    return {
        "overview": overview,
        "attention": attention_out,
        "active_work": active_work,
        "pending_approvals": pending_out,
        "risk_summary": risk_summary,
        "channels": channels_section,
        "recommendations": recommendations,
        "quiet": quiet,
        "hours": int(window_h),
        "orchestration": _orchestration_snapshot(db, uid),
        "maintenance": {
            "sql_purge_enabled": bool(get_settings().nexa_mission_control_sql_purge),
        },
    }


def _build_recommendations(
    *,
    overview: dict[str, Any],
    pending_perms: int,
    ch_rows: list[dict[str, Any]],
    trust_blocked: int,
    failed_jobs: int,
    gateway_failures: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if pending_perms > 0:
        out.append(
            {
                "id": "rec-pending-approvals",
                "type": "recommendation",
                "title": f"Review {pending_perms} pending approval(s)",
                "description": "Approve or deny permission requests in Pending approvals below.",
                "status": None,
                "risk_level": None,
                "channel": None,
                "score": score_mission_item({"type": "recommendation"}),
                "created_at": None,
                "permission_id": None,
                "job_id": None,
            }
        )
    ch_rec = 0
    for r in ch_rows:
        if ch_rec >= 3:
            break
        if not r.get("configured") or (r.get("health") or "") == "missing_config":
            miss = r.get("missing") or []
            hint = ", ".join(miss[:3]) if miss else "required env vars"
            out.append(
                {
                    "id": f"rec-ch-{r.get('channel')}",
                    "type": "recommendation",
                    "title": f"Configure channel: {r.get('label') or r.get('channel')}",
                    "description": f"Missing: {hint}",
                    "status": None,
                    "risk_level": None,
                    "channel": str(r.get("channel")),
                    "score": score_mission_item({"type": "recommendation"}),
                    "created_at": None,
                    "permission_id": None,
                    "job_id": None,
                }
            )
            ch_rec += 1
    if gateway_failures > 0:
        out.append(
            {
                "id": "rec-gateway-fail",
                "type": "recommendation",
                "title": "Check failed outbound channel messages",
                "description": f"{gateway_failures} outbound failure(s) recorded in the selected window.",
                "status": None,
                "risk_level": None,
                "channel": None,
                "score": score_mission_item({"type": "recommendation"}),
                "created_at": None,
                "permission_id": None,
                "job_id": None,
            }
        )
    if trust_blocked > 0:
        out.append(
            {
                "id": "rec-trust-blocked",
                "type": "recommendation",
                "title": "Inspect blocked external sends",
                "description": f"{trust_blocked} blocked external send(s) in Trust activity.",
                "status": None,
                "risk_level": None,
                "channel": None,
                "score": score_mission_item({"type": "recommendation"}),
                "created_at": None,
                "permission_id": None,
                "job_id": None,
            }
        )
    if failed_jobs > 0:
        out.append(
            {
                "id": "rec-failed-jobs",
                "type": "recommendation",
                "title": "Inspect failed jobs",
                "description": f"{failed_jobs} job(s) in failed state.",
                "status": None,
                "risk_level": None,
                "channel": None,
                "score": score_mission_item({"type": "recommendation"}),
                "created_at": None,
                "permission_id": None,
                "job_id": None,
            }
        )
    return out[:25]
