"""Topological-ish worker loop: ready queued agents when dependencies are satisfied."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.nexa_next_runtime import NexaMissionTask
from app.services.events.bus import publish
from app.services.logging.logger import get_logger
from app.services.workers.runner import run_agent

_log = get_logger("worker")


def run_until_complete(
    agents: list[dict[str, Any]],
    mission: dict[str, Any],
    db: Session,
    *,
    max_runtime_seconds: float | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """
    Run agents until no queued work remains or ``max_runtime_seconds`` elapses.

    Returns ``(agents, timed_out)``.
    """
    _ = mission
    completed: set[str] = set()

    deadline: float | None = None
    if max_runtime_seconds is not None and max_runtime_seconds > 0:
        deadline = time.monotonic() + float(max_runtime_seconds)

    mission_id = agents[0].get("mission_id") if agents else None

    while True:
        if deadline is not None and time.monotonic() > deadline:
            _log.warning("mission runtime exceeded mission_id=%s", mission_id)
            _cancel_remaining(agents, db, mission_id=str(mission_id) if mission_id else "")
            publish(
                {
                    "type": "mission.timeout",
                    "mission_id": mission_id,
                    "detail": "NEXA_MISSION_MAX_RUNTIME_SECONDS exceeded",
                }
            )
            return agents, True

        progress = False

        for agent in agents:
            if agent["status"] != "queued":
                continue

            if any(dep not in completed for dep in agent["depends_on"]):
                continue

            pk = agent.get("task_pk")
            started_at = datetime.now(timezone.utc)
            if pk is not None:
                row = db.get(NexaMissionTask, pk)
                if row is not None:
                    row.status = "running"
                    row.started_at = started_at
                    db.commit()

            publish(
                {
                    "type": "task.started",
                    "agent": agent["handle"],
                    "mission_id": agent.get("mission_id"),
                }
            )

            agent["status"] = "running"
            t0 = time.perf_counter()
            agent["output"] = run_agent(agent, db)
            dur_ms = (time.perf_counter() - t0) * 1000.0
            agent["status"] = "completed"

            if pk is not None:
                row = db.get(NexaMissionTask, pk)
                if row is not None:
                    row.status = "completed"
                    row.output_json = agent["output"]
                    row.duration_ms = dur_ms
                    db.commit()

            publish(
                {
                    "type": "task.completed",
                    "agent": agent["handle"],
                    "mission_id": agent.get("mission_id"),
                }
            )

            completed.add(agent["handle"])
            progress = True

        if not progress:
            break

    return agents, False


def _cancel_remaining(agents: list[dict[str, Any]], db: Session, *, mission_id: str) -> None:
    for agent in agents:
        if agent["status"] != "queued":
            continue
        pk = agent.get("task_pk")
        agent["status"] = "cancelled"
        agent["output"] = {
            "type": "mission_timeout",
            "detail": "Mission exceeded max runtime; task not started.",
            "mission_id": mission_id,
        }
        if pk is not None:
            row = db.get(NexaMissionTask, pk)
            if row is not None:
                row.status = "cancelled"
                row.output_json = agent["output"]
        db.commit()


__all__ = ["run_until_complete"]
