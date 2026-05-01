"""Autonomous planning hook — follow-ups and system ticks when NEXA_AUTONOMOUS_MODE (Phase 43)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.events.unified_event import emit_unified_event


def autonomous_planner(db: Session | None = None) -> dict[str, Any]:
    """
    Single entry the supervisor can call on each cycle. Emits a unified event so Mission Control
    can schedule work; expand with memory-aware planning when ready.
    """
    _ = db
    if not getattr(get_settings(), "nexa_autonomous_mode", False):
        return {"ok": False, "skipped": True, "reason": "autonomous_mode_off"}
    tid = str(uuid.uuid4())
    emit_unified_event(
        "autonomous.planner.tick",
        task_id=tid,
        payload={"source": "operator_supervisor"},
    )
    return {"ok": True, "task_id": tid}


__all__ = ["autonomous_planner"]
