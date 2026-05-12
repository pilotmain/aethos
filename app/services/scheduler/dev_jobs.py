# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Bounded dev jobs dispatched from scheduler rows (Phase 24–25)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.nexa_scheduler_job import NexaSchedulerJob
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway

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

    gctx = GatewayContext.from_channel(
        uid,
        "scheduler",
        {
            "via_gateway": True,
            "scheduler_job_id": row.id,
            "scheduled_dev_mission": payload,
        },
    )
    NexaGateway().handle_message(gctx, "", db=db)
    return True


__all__ = [
    "parse_dev_mission_payload",
    "execute_dev_mission_job",
    "SCHEDULER_DEV_JOB_TYPES",
    "DEFAULT_GOALS",
]
