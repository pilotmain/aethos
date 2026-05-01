"""Phase 11 — system health and lightweight metrics."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.db import get_db
from app.services.metrics.runtime import snapshot, uptime_seconds

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def system_health(db: Session = Depends(get_db)) -> dict:
    """Deep health: DB ping + provider readiness hints."""
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    s = get_settings()
    providers = "ready"
    if s.nexa_disable_external_calls:
        providers = "external_disabled"
    elif not ((s.openai_api_key or "").strip() or (s.anthropic_api_key or "").strip()):
        providers = "no_remote_keys"

    overall = "ok" if db_status == "connected" else "degraded"

    return {
        "status": overall,
        "db": db_status,
        "providers": providers,
        "uptime_seconds": round(uptime_seconds(), 3),
        "version": s.nexa_release_version,
    }


@router.get("/metrics")
def system_metrics() -> dict:
    """In-process counters (reset on process restart)."""
    return snapshot()


__all__ = ["router"]
