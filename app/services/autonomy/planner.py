# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Autonomous planning hook — follow-ups and system ticks when NEXA_AUTONOMOUS_MODE (Phase 43–44)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.autonomy.decision import autonomous_decision_loop
from app.services.events.unified_event import emit_unified_event


def autonomous_planner(db: Session | None = None) -> dict[str, Any]:
    """
    Single entry the supervisor can call on each cycle: heartbeat event plus Phase 44 decision loop.
    """
    if not getattr(get_settings(), "nexa_autonomous_mode", False):
        return {"ok": False, "skipped": True, "reason": "autonomous_mode_off"}

    tid = str(uuid.uuid4())
    emit_unified_event(
        "autonomous.planner.tick",
        task_id=tid,
        payload={"source": "operator_supervisor"},
    )

    def _run(session: Session) -> dict[str, Any]:
        loop = autonomous_decision_loop(session, user_id=None)
        return {"ok": True, "task_id": tid, "decision": loop}

    if db is not None:
        return _run(db)

    from app.core.db import SessionLocal

    with SessionLocal() as session:
        return _run(session)


__all__ = ["autonomous_planner"]
