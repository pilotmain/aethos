"""Unified task model — missions, dev runs, scheduler jobs, and system hooks share one shape."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NexaTask:
    """Canonical task record for routing, events, and autonomy (Phase 43)."""

    id: str
    type: str  # dev | mission | system | scheduled
    input: str
    context: dict[str, Any] = field(default_factory=dict)
    state: str = "pending"
    result: dict[str, Any] | None = None

    @classmethod
    def from_scheduler_dev_payload(
        cls,
        payload: dict[str, Any],
        *,
        job_id: str | None = None,
    ) -> NexaTask:
        goal = str(payload.get("goal") or "").strip()
        wid = str(payload.get("workspace_id") or "").strip()
        kind = str(payload.get("type") or "dev_mission")
        tid = (job_id or "").strip() or str(uuid.uuid4())
        return cls(
            id=tid,
            type="scheduled",
            input=goal,
            context={
                "workspace_id": wid,
                "job_kind": kind,
                "scheduler_payload": dict(payload),
            },
        )

    @classmethod
    def from_long_running_row(cls, *, user_id: str, session_key: str, iteration: int, goal: str) -> NexaTask:
        return cls(
            id=f"lr:{user_id}:{session_key}:{iteration}",
            type="system",
            input=(goal or "").strip(),
            context={"session_key": session_key, "user_id": user_id, "iteration": iteration},
        )


__all__ = ["NexaTask"]
