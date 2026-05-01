"""Topological-ish worker loop: ready queued agents when dependencies are satisfied."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.nexa_next_runtime import NexaMissionTask
from app.services.events.envelope import emit_runtime_event
from app.services.logging.logger import get_logger
from app.services.workers.runner import run_agent

_log = get_logger("worker")


def _run_single_agent(agent: dict[str, Any], db: Session, *, deadline: float | None) -> bool:
    """Execute one agent on ``db``. Returns False if deadline exceeded before completion."""
    if deadline is not None and time.monotonic() > deadline:
        return False

    pk = agent.get("task_pk")
    started_at = datetime.now(timezone.utc)
    if pk is not None:
        row = db.get(NexaMissionTask, pk)
        if row is not None:
            row.status = "running"
            row.started_at = started_at
            db.commit()

    emit_runtime_event(
        "task.started",
        mission_id=str(agent.get("mission_id") or "") or None,
        agent=str(agent.get("handle") or ""),
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

    emit_runtime_event(
        "task.completed",
        mission_id=str(agent.get("mission_id") or "") or None,
        agent=str(agent.get("handle") or ""),
    )
    return True


def _run_agent_thread(agent_snapshot: dict[str, Any], *, deadline: float | None) -> dict[str, Any]:
    """Session per thread (for parallel wave). Returns merged agent row fields."""
    from app.core.db import SessionLocal

    ag = dict(agent_snapshot)
    with SessionLocal() as db:
        _run_single_agent(ag, db, deadline=deadline)
    return ag


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
    s = get_settings()
    use_parallel = bool(
        getattr(s, "nexa_mission_parallel_tasks", False)
        and not (s.database_url or "").startswith("sqlite")
    )

    while True:
        if deadline is not None and time.monotonic() > deadline:
            _log.warning("mission runtime exceeded mission_id=%s", mission_id)
            _cancel_remaining(agents, db, mission_id=str(mission_id) if mission_id else "")
            emit_runtime_event(
                "mission.timeout",
                mission_id=str(mission_id) if mission_id else None,
                payload={"detail": "NEXA_MISSION_MAX_RUNTIME_SECONDS exceeded"},
            )
            return agents, True

        ready = [
            a
            for a in agents
            if a["status"] == "queued"
            and not any(dep not in completed for dep in a["depends_on"])
        ]
        if not ready:
            break

        progress = False

        if use_parallel and len(ready) > 1:
            max_workers = min(8, len(ready))
            handle_map = {a["handle"]: a for a in agents}
            snapshots = [dict(a) for a in ready]
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = [
                    pool.submit(_run_agent_thread, snap, deadline=deadline) for snap in snapshots
                ]
                for fut in as_completed(futures):
                    ag_done = fut.result()
                    h = str(ag_done.get("handle") or "")
                    tgt = handle_map.get(h)
                    if tgt is None:
                        continue
                    tgt["status"] = ag_done.get("status")
                    tgt["output"] = ag_done.get("output")
                    completed.add(h)
                    progress = True
        else:
            for agent in ready:
                if not _run_single_agent(agent, db, deadline=deadline):
                    continue
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
