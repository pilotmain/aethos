"""Bounded ``dev_mission`` jobs dispatched from scheduler rows (Phase 24)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.nexa_scheduler_job import NexaSchedulerJob
from app.services.dev_runtime.service import run_dev_mission


def parse_dev_mission_payload(mission_text: str) -> dict[str, Any] | None:
    raw = (mission_text or "").strip()
    if not raw.startswith("{"):
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if payload.get("type") != "dev_mission":
        return None
    return payload


def execute_dev_mission_job(db: Session, row: NexaSchedulerJob) -> bool:
    """
    Run a dev mission from a scheduler row. Returns True if this row was handled.

    Scheduled jobs are conservative: no push, no commit, no write by default.
    """
    payload = parse_dev_mission_payload(row.mission_text or "")
    if payload is None:
        return False
    uid = (row.user_id or "").strip()
    wid = str(payload.get("workspace_id") or "").strip()
    goal = str(payload.get("goal") or "").strip()
    if not uid or not wid or not goal:
        return True
    pref = payload.get("preferred_agent")
    allow_write = bool(payload.get("allow_write", False))
    run_dev_mission(
        db,
        uid,
        wid,
        goal,
        auto_pr=False,
        preferred_agent=str(pref) if pref else None,
        allow_write=allow_write,
        allow_commit=False,
        allow_push=False,
        cost_budget_usd=0.0,
        schedule=None,
        from_scheduler=True,
    )
    return True


__all__ = ["parse_dev_mission_payload", "execute_dev_mission_job"]
