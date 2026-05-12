# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""P1 trust dashboard JSON API — activity feed + aggregates (backend-first)."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.services.trust_audit_constants import TRUST_DASHBOARD_CORE_EVENT_TYPES
from app.services.trust_audit_read_model import query_trust_activity, summarize_trust_activity

router = APIRouter(prefix="/trust", tags=["trust"])


@router.get("/activity")
def trust_activity(
    user_id: str = Depends(get_valid_web_user_id),
    db: Session = Depends(get_db),
    hours: float = Query(default=168.0, ge=0.25, le=8760.0, description="Look back this many hours"),
    limit: int = Query(default=100, ge=1, le=500),
    event_type: list[str] | None = Query(
        default=None,
        description="Repeat parameter to restrict to known trust event types (tabs/filters)",
    ),
) -> dict:
    since = datetime.utcnow() - timedelta(hours=hours)
    types_filter: set[str] | None = None
    if event_type:
        unknown = set(event_type) - TRUST_DASHBOARD_CORE_EVENT_TYPES
        if unknown:
            raise HTTPException(
                status_code=400,
                detail={"error": "unsupported_event_type", "unknown": sorted(unknown)},
            )
        types_filter = set(event_type)
    events = query_trust_activity(
        db, user_id, since=since, limit=limit, event_types=types_filter
    )
    return {
        "since": since.isoformat() + "Z",
        "hours": hours,
        "event_types_filter": sorted(types_filter) if types_filter else None,
        "events": events,
    }


@router.get("/summary")
def trust_summary(
    user_id: str = Depends(get_valid_web_user_id),
    db: Session = Depends(get_db),
    hours: float = Query(default=24.0, ge=0.25, le=8760.0),
    recent_limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    s = summarize_trust_activity(db, user_id, window_hours=hours, recent_limit=recent_limit)
    return {
        "window_hours": s.window_hours,
        "counts": {
            "permission_uses": s.permission_uses,
            "network_external_send_allowed": s.network_send_allowed,
            "network_external_send_blocked": s.network_send_blocked,
            "sensitive_egress_warnings": s.sensitive_egress_warnings,
            "host_executor_blocks": s.host_executor_blocks,
            "safety_enforcement_paths": s.enforcement_paths,
        },
        "recent_events": s.recent_events,
    }
