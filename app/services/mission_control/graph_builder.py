# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Build nodes/edges for Mission Control visual graph from execution snapshot."""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from typing import Any

_GRAPH_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
_MAX_GRAPH_CACHE_ENTRIES = 64


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
                    "execution_verified": task.get("execution_verified"),
                    "execution_state": task.get("execution_state"),
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


def _graph_cache_key(state: dict[str, Any]) -> str:
    slim = {
        "missions": [
            {"id": (m or {}).get("id"), "status": (m or {}).get("status")}
            for m in (state.get("missions") or [])[:80]
            if isinstance(m, dict)
        ],
        "tasks": [
            {
                "mission_id": (t or {}).get("mission_id"),
                "agent_handle": (t or {}).get("agent_handle"),
                "status": (t or {}).get("status"),
                "depends_on": (t or {}).get("depends_on"),
                "execution_verified": (t or {}).get("execution_verified"),
                "execution_state": (t or {}).get("execution_state"),
            }
            for t in (state.get("tasks") or [])
            if isinstance(t, dict)
        ],
    }
    raw = json.dumps(slim, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def build_graph_cached(state: dict[str, Any]) -> dict[str, Any]:
    """Memoized graph build keyed by missions/tasks signature (Phase 14)."""
    key = _graph_cache_key(state)
    if key in _GRAPH_CACHE:
        _GRAPH_CACHE.move_to_end(key)
        return dict(_GRAPH_CACHE[key])
    out = build_graph(state)
    _GRAPH_CACHE[key] = out
    _GRAPH_CACHE.move_to_end(key)
    while len(_GRAPH_CACHE) > _MAX_GRAPH_CACHE_ENTRIES:
        _GRAPH_CACHE.popitem(last=False)
    return dict(out)


def clear_graph_cache() -> None:
    """Test helper / manual invalidation."""
    _GRAPH_CACHE.clear()


__all__ = ["build_graph", "build_graph_cached", "clear_graph_cache"]
