"""Bounded dev jobs dispatched from scheduler rows (Phase 24–25)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.nexa_scheduler_job import NexaSchedulerJob
from app.services.dev_runtime.service import run_dev_mission

# Recognized scheduler payload ``type`` (or ``dev_job`` + ``job_kind``).
SCHEDULER_DEV_JOB_TYPES = frozenset(
    {
        "dev_mission",
        "nightly_test",
        "nightly_fix_attempt",
        "weekly_pr_review",
        "dependency_check",
    }
)

DEFAULT_GOALS: dict[str, str] = {
    "nightly_test": "Run tests and summarize failures",
    "nightly_fix_attempt": "Attempt bounded fixes for failing tests",
    "weekly_pr_review": "Summarize recent changes for PR review",
    "dependency_check": "Scan dependency manifests for obvious issues",
}


def parse_dev_mission_payload(mission_text: str) -> dict[str, Any] | None:
    raw = (mission_text or "").strip()
    if not raw.startswith("{"):
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    t = str(payload.get("type") or "").strip()
    if t == "dev_job":
        jk = str(payload.get("job_kind") or "").strip()
        if jk in SCHEDULER_DEV_JOB_TYPES:
            out = dict(payload)
            out["type"] = jk
            return out
        return None
    if t in SCHEDULER_DEV_JOB_TYPES:
        return payload
    return None


def execute_dev_mission_job(db: Session, row: NexaSchedulerJob) -> bool:
    """
    Run a dev mission from a scheduler row. Returns True if this row was handled.

    Scheduled jobs never push, merge, or deploy; default agent is ``local_stub``.
    """
    payload = parse_dev_mission_payload(row.mission_text or "")
    if payload is None:
        return False
    uid = (row.user_id or "").strip()
    wid = str(payload.get("workspace_id") or "").strip()
    if not uid or not wid:
        return True

    kind = str(payload.get("type") or "dev_mission")
    goal = str(payload.get("goal") or "").strip() or DEFAULT_GOALS.get(kind, "Scheduled dev mission")

    max_it = payload.get("max_iterations")
    if max_it is None:
        max_it = 3 if "fix" in kind else 1

    pref = payload.get("preferred_agent") or "local_stub"
    allow_write = bool(payload.get("allow_write", False))

    run_dev_mission(
        db,
        uid,
        wid,
        goal,
        auto_pr=False,
        preferred_agent=str(pref),
        allow_write=allow_write,
        allow_commit=False,
        allow_push=False,
        cost_budget_usd=0.0,
        max_iterations=int(max_it),
        schedule=None,
        from_scheduler=True,
    )
    return True


__all__ = [
    "parse_dev_mission_payload",
    "execute_dev_mission_job",
    "SCHEDULER_DEV_JOB_TYPES",
    "DEFAULT_GOALS",
]
