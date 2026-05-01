"""Topological-ish worker loop: ready queued agents when dependencies are satisfied."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.nexa_next_runtime import NexaMissionTask
from app.services.events.bus import publish
from app.services.workers.runner import run_agent


def run_until_complete(
    agents: list[dict[str, Any]],
    mission: dict[str, Any],
    db: Session,
) -> list[dict[str, Any]]:
    _ = mission
    completed: set[str] = set()

    while True:
        progress = False

        for agent in agents:
            if agent["status"] != "queued":
                continue

            if any(dep not in completed for dep in agent["depends_on"]):
                continue

            pk = agent.get("task_pk")
            if pk is not None:
                row = db.get(NexaMissionTask, pk)
                if row is not None:
                    row.status = "running"
                    db.commit()

            publish(
                {
                    "type": "task.started",
                    "agent": agent["handle"],
                    "mission_id": agent.get("mission_id"),
                }
            )

            agent["status"] = "running"
            agent["output"] = run_agent(agent, db)
            agent["status"] = "completed"

            if pk is not None:
                row = db.get(NexaMissionTask, pk)
                if row is not None:
                    row.status = "completed"
                    row.output_json = agent["output"]
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

    return agents
