"""
Dashboard-oriented reads over ``audit_logs`` — P1 trust surface backend.

Filters use indexed columns where possible; correlation lives in ``metadata_json``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from urllib.parse import urlparse

from app.models.audit_log import AuditLog
from app.services.trust_audit_constants import (
    ACCESS_HOST_EXECUTOR_BLOCKED,
    ACCESS_PERMISSION_DENIED,
    ACCESS_PERMISSION_USED,
    ACCESS_SENSITIVE_EGRESS_WARNING,
    ACCESS_SURFACE_DENIED_LEGACY,
    NETWORK_EXTERNAL_SEND_ALLOWED,
    NETWORK_EXTERNAL_SEND_BLOCKED,
    SAFETY_ENFORCEMENT_PATH,
    TRUST_DASHBOARD_CORE_EVENT_TYPES,
    TRUST_UI_STATUS_ALLOWED,
    TRUST_UI_STATUS_BLOCKED,
    TRUST_UI_STATUS_WARNING,
)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat() + "Z"


def audit_row_to_event(row: AuditLog) -> dict[str, Any]:
    md = dict(row.metadata_json or {})
    ui_status = _infer_ui_status(row.event_type, md)
    dest = _normalize_destination_display(row.event_type, md)
    return {
        "id": row.id,
        "event_type": row.event_type,
        "actor": row.actor,
        "message": row.message[:2000],
        "user_id": row.user_id,
        "job_id": row.job_id,
        "created_at": _iso(row.created_at),
        "metadata": md,
        "workflow_id": md.get("workflow_id"),
        "run_id": md.get("run_id"),
        "execution_id": md.get("execution_id"),
        "status": ui_status,
        "destination": dest,
        "sensitivity_level": md.get("sensitivity_level"),
        # Channel lineage (optional; Trust UI — historical rows may omit)
        "channel": md.get("channel"),
        "channel_user_id": md.get("channel_user_id"),
        "channel_message_id": md.get("channel_message_id"),
        "channel_thread_id": md.get("channel_thread_id"),
        "channel_chat_id": md.get("channel_chat_id"),
    }


def _infer_ui_status(event_type: str, md: dict[str, Any]) -> str:
    """Stable UI contract: exactly ``allowed`` | ``blocked`` | ``warning``."""
    et = event_type or ""
    if et in (
        NETWORK_EXTERNAL_SEND_BLOCKED,
        ACCESS_HOST_EXECUTOR_BLOCKED,
        ACCESS_PERMISSION_DENIED,
        ACCESS_SURFACE_DENIED_LEGACY,
    ) or md.get("allowed") is False:
        return TRUST_UI_STATUS_BLOCKED
    if et == ACCESS_SENSITIVE_EGRESS_WARNING or et.endswith(".warning"):
        return TRUST_UI_STATUS_WARNING
    return TRUST_UI_STATUS_ALLOWED


def _normalize_destination_display(event_type: str, md: dict[str, Any]) -> str | None:
    """Hostname for URLs; short labels for permissions / host actions."""
    et = event_type or ""
    if "external_send" in et or et == ACCESS_SENSITIVE_EGRESS_WARNING:
        h = md.get("hostname")
        if h:
            return str(h)[:200]
        ext = (md.get("external_target") or "").strip()
        if ext.startswith(("http://", "https://")):
            try:
                host = urlparse(ext).hostname
                return (host or ext)[:200]
            except Exception:  # noqa: BLE001
                return ext[:200]
        if ext:
            return ext[:200]
        fu = (md.get("final_url") or "").strip()
        if fu.startswith(("http://", "https://")):
            try:
                return (urlparse(fu).hostname or fu)[:200]
            except Exception:  # noqa: BLE001
                return fu[:200]
        return None
    if et.startswith("access.permission") or et == ACCESS_HOST_EXECUTOR_BLOCKED:
        tp = md.get("target_preview")
        if tp:
            return str(tp)[:200]
        ha = md.get("host_action")
        if ha:
            return str(ha)[:120]
        sc = md.get("scope")
        if sc:
            return str(sc)[:120]
    return None


def query_trust_activity(
    db: Session,
    user_id: str,
    *,
    event_types: set[str] | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Recent trust events for one user (newest first)."""
    lim = min(max(int(limit), 1), 500)
    if event_types is None:
        types = TRUST_DASHBOARD_CORE_EVENT_TYPES
    else:
        types = event_types
    q = select(AuditLog).where(AuditLog.user_id == user_id, AuditLog.event_type.in_(types))
    if since is not None:
        q = q.where(AuditLog.created_at >= since)
    if until is not None:
        q = q.where(AuditLog.created_at <= until)
    q = q.order_by(AuditLog.created_at.desc()).limit(lim)
    rows = db.execute(q).scalars().all()
    return [audit_row_to_event(r) for r in rows]


@dataclass
class TrustActivitySummary:
    """Minimal aggregates for dashboard cards."""

    window_hours: float
    permission_uses: int
    network_send_allowed: int
    network_send_blocked: int
    sensitive_egress_warnings: int
    host_executor_blocks: int
    enforcement_paths: int
    recent_events: list[dict[str, Any]]


def summarize_trust_activity(
    db: Session,
    user_id: str,
    *,
    window_hours: float = 24.0,
    recent_limit: int = 20,
) -> TrustActivitySummary:
    """Counts + recent rows for trust overview."""
    since = datetime.utcnow() - timedelta(hours=max(window_hours, 0.01))

    def _count(event_type: str) -> int:
        q = (
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.user_id == user_id,
                AuditLog.event_type == event_type,
                AuditLog.created_at >= since,
            )
        )
        return int(db.execute(q).scalar() or 0)

    recent = query_trust_activity(
        db,
        user_id,
        since=since,
        limit=min(max(int(recent_limit), 1), 100),
    )

    return TrustActivitySummary(
        window_hours=window_hours,
        permission_uses=_count(ACCESS_PERMISSION_USED),
        network_send_allowed=_count(NETWORK_EXTERNAL_SEND_ALLOWED),
        network_send_blocked=_count(NETWORK_EXTERNAL_SEND_BLOCKED),
        sensitive_egress_warnings=_count(ACCESS_SENSITIVE_EGRESS_WARNING),
        host_executor_blocks=_count(ACCESS_HOST_EXECUTOR_BLOCKED),
        enforcement_paths=_count(SAFETY_ENFORCEMENT_PATH),
        recent_events=recent,
    )
