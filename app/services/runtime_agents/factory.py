"""Build in-memory agent rows from a parsed mission dict."""

from __future__ import annotations

from typing import Any


def normalize_handle(name: str) -> str:
    return (name or "").lower().replace(" ", "_").replace("-", "_")


def create_runtime_agents(
    mission: dict[str, Any],
    user_id: str,
    *,
    mission_id: str | None = None,
) -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []
    steps = mission.get("agents") or mission.get("tasks") or []
    for step in steps:
        if "agent_handle" in step:
            role = str(step.get("agent_handle") or "agent")
        else:
            role = str(step.get("role") or "agent")
        handle = normalize_handle(role)
        if handle in ("http", "https"):
            continue
        agents.append(
            {
                "handle": handle,
                "role": role,
                "task": step["task"],
                "depends_on": [normalize_handle(x) for x in step.get("depends_on", [])],
                "status": "queued",
                "output": None,
                "user_id": user_id,
                "mission_id": mission_id,
            }
        )
    return agents
