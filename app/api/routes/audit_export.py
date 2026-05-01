"""Governance audit export (Phase 13)."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.audit_service import audit
from app.services.governance_taxonomy import EVENT_AUDIT_EXPORT_CREATED

router = APIRouter(prefix="/audit", tags=["audit"])


def _assert_exporter(db: Session, user_id: str) -> None:
    if not get_settings().nexa_governance_enabled:
        return
    u = db.get(User, user_id)
    role = str((u.governance_role if u else "") or "").strip().lower()
    if role not in ("owner", "admin", "auditor"):
        raise HTTPException(status_code=403, detail="Owner, admin, or auditor role required for export")


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


@router.get("/export")
def export_audit(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
    format: Annotated[Literal["json", "csv"], Query()] = "json",
    from_date: Annotated[str | None, Query(alias="from")] = None,
    to_date: Annotated[str | None, Query(alias="to")] = None,
    channel: str | None = None,
    event_type: str | None = None,
    user_id: str | None = None,
) -> Response:
    _assert_exporter(db, app_user_id)
    t0 = _parse_dt(from_date)
    t1 = _parse_dt(to_date)
    stmt = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(5000)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == (user_id or "").strip()[:64])
    if event_type:
        stmt = stmt.where(AuditLog.event_type == (event_type or "").strip()[:64])
    if t0:
        stmt = stmt.where(AuditLog.created_at >= t0)
    if t1:
        stmt = stmt.where(AuditLog.created_at <= t1)
    rows = list(db.scalars(stmt).all())
    if channel:
        c = (channel or "").strip().lower()
        filtered = []
        for r in rows:
            md = dict(r.metadata_json or {})
            if str(md.get("channel") or "").lower() == c:
                filtered.append(r)
        rows = filtered[:3000]

    audit(
        db,
        event_type=EVENT_AUDIT_EXPORT_CREATED,
        actor="governance",
        user_id=app_user_id,
        message=f"audit export format={format} rows={len(rows)}",
        metadata={"format": format, "row_count": len(rows)},
    )

    def row_dict(r: AuditLog) -> dict[str, object]:
        md = dict(r.metadata_json or {})
        status_val = md.get("status")
        if status_val is None and r.event_type:
            status_val = str(r.event_type)
        return {
            "id": r.id,
            "timestamp": r.created_at.isoformat() if r.created_at else "",
            "user_id": r.user_id,
            "event_type": r.event_type,
            "status": status_val if status_val is not None else "",
            "actor": r.actor,
            "message": (r.message or "")[:500],
            "channel": md.get("channel"),
            "channel_user_id": md.get("channel_user_id"),
            "metadata": md,
        }

    out_rows = [row_dict(r) for r in rows]

    if format == "json":
        return Response(
            content=json.dumps({"events": out_rows}, indent=2, default=str),
            media_type="application/json",
        )

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        ["id", "timestamp", "user_id", "event_type", "status", "actor", "channel", "channel_user_id", "message"]
    )
    for item in out_rows:
        w.writerow(
            [
                item["id"],
                item["timestamp"],
                item.get("user_id") or "",
                item["event_type"],
                item.get("status") or "",
                item["actor"],
                item.get("channel") or "",
                item.get("channel_user_id") or "",
                str(item.get("message") or "")[:500],
            ]
        )
    return PlainTextResponse(content=buf.getvalue(), media_type="text/csv")
