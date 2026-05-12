# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 11 — system health and lightweight metrics."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.services.metrics.runtime import snapshot, uptime_seconds
from app.services.mission_control.nexa_next_state import _runtime_hints

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

    rt = _runtime_hints()
    provider_tags = ["local_stub"]
    if (s.openai_api_key or "").strip():
        provider_tags.append("openai")
    if (s.anthropic_api_key or "").strip():
        provider_tags.append("anthropic")

    strict_priv = bool(rt.get("strict_privacy_mode"))
    privacy_mode = "strict" if strict_priv else "standard"
    scheduler = "running" if db_status == "connected" else "unknown"
    runtime_ready = "ready" if overall == "ok" else "degraded"

    return {
        "ok": overall == "ok",
        "status": overall,
        "db": db_status,
        "scheduler": scheduler,
        "privacy_mode": privacy_mode,
        "runtime": runtime_ready,
        "providers": providers,
        "uptime_seconds": round(uptime_seconds(), 3),
        "version": s.nexa_release_version,
        "offline_mode": bool(rt.get("offline_mode")),
        "strict_privacy": strict_priv,
        "provider_tags": provider_tags,
    }


@router.get("/metrics")
def system_metrics() -> dict:
    """In-process counters (reset on process restart)."""
    return snapshot()


__all__ = ["router"]
