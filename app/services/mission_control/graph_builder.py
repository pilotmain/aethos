"""Build nodes/edges for Mission Control visual graph from execution snapshot."""

from __future__ import annotations

from typing import Any


def _scoped_id(mission_id: str, handle: str) -> str:
    return f"{mission_id}:{handle}"


def _task_mission_bucket(task: dict[str, Any]) -> str:
    """Prefer DB ``mission_id``; fall back to spawn group or assignment id for legacy runtime tasks."""
    mid = str(task.get("mission_id") or "").strip()
    if mid:
        return mid
    sg = str(task.get("spawn_group_id") or "").strip()
    if sg:
        return f"spawn:{sg}"
    tid = task.get("id")
    if tid is not None:
        return f"assign:{tid}"
    return "default"


def build_graph(state: dict[str, Any]) -> dict[str, Any]:
    """
    Derive a directed graph from ``build_execution_snapshot`` output.

    Nodes are mission tasks (agents); edges follow ``depends_on`` within the same mission.
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen: set[str] = set()

    for task in state.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        mission_id = _task_mission_bucket(task)
        handle = str(task.get("agent_handle") or "").strip()
        if not handle:
            continue

        nid = _scoped_id(mission_id, handle)
        if nid not in seen:
            seen.add(nid)
            nodes.append(
                {
                    "id": nid,
                    "label": str(task.get("role") or handle),
                    "status": str(task.get("status") or "unknown"),
                    "handle": handle,
                    "mission_id": mission_id,
                }
            )

        for dep in task.get("depends_on") or []:
            dep_h = str(dep).strip()
            if not dep_h:
                continue
            edges.append({"from": _scoped_id(mission_id, dep_h), "to": nid})

    # Legacy shape (nested missions + agents) — optional fallback for older payloads.
    for mission in state.get("missions") or []:
        if not isinstance(mission, dict):
            continue
        agents = mission.get("agents")
        if not isinstance(agents, list):
            continue
        mid = str(mission.get("id") or mission.get("mission_id") or "").strip() or "legacy"
        for agent in agents:
            if not isinstance(agent, dict):
                continue
            handle = str(agent.get("handle") or "").strip()
            if not handle:
                continue
            nid = _scoped_id(mid, handle)
            if nid not in seen:
                seen.add(nid)
                nodes.append(
                    {
                        "id": nid,
                        "label": str(agent.get("role") or handle),
                        "status": str(agent.get("status") or "unknown"),
                        "handle": handle,
                        "mission_id": mid,
                    }
                )
            for dep in agent.get("depends_on") or []:
                dep_h = str(dep).strip()
                if dep_h:
                    edges.append({"from": _scoped_id(mid, dep_h), "to": nid})

    return {"nodes": nodes, "edges": edges}
