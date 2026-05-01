"""Phase 10 — admin introspection (disabled unless ``NEXA_ADMIN_ENDPOINTS_ENABLED``)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models.nexa_next_runtime import NexaExternalCall
from app.services.mission_control.nexa_next_state import STATE

router = APIRouter(prefix="/admin", tags=["admin-privacy"])


def _require_admin() -> None:
    if not get_settings().nexa_admin_endpoints_enabled:
        # Hide existence when disabled (avoid enumeration).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@router.get("/privacy/events")
def admin_privacy_events() -> list:
    _require_admin()
    return list(STATE.get("privacy_events") or [])


@router.get("/external-calls")
def admin_external_calls(
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=2000),
) -> list[dict]:
    _require_admin()
    rows = list(
        db.scalars(select(NexaExternalCall).order_by(NexaExternalCall.created_at.desc()).limit(limit)).all()
    )
    return [
        {
            "id": r.id,
            "provider": r.provider,
            "agent": r.agent,
            "mission_id": r.mission_id,
            "user_id": r.user_id,
            "blocked": r.blocked,
            "error": r.error,
            "redactions": r.redactions or [],
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
