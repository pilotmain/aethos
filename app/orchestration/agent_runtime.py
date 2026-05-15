"""Agent runtime registry (subset of OpenClaw multi-agent parity)."""

from __future__ import annotations

import time
import uuid
from typing import Any


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def register_agent(st: dict[str, Any], agent: dict[str, Any] | None = None) -> str:
    agents = st.setdefault("agents", [])
    if not isinstance(agents, list):
        st["agents"] = []
        agents = st["agents"]
    aid = str((agent or {}).get("id") or uuid.uuid4())
    row = dict(agent or {})
    row["id"] = aid
    row.setdefault("registered_at", _now_iso())
    row.setdefault("active_tasks", [])
    row.setdefault("delegated_tasks", [])
    row.setdefault("execution_state", "idle")
    agents.append(row)
    return aid


def attach_task_to_agent(st: dict[str, Any], agent_id: str, task_id: str, delegated: bool = False) -> None:
    agents = st.get("agents")
    if not isinstance(agents, list):
        return
    for a in agents:
        if not isinstance(a, dict):
            continue
        if str(a.get("id")) != agent_id:
            continue
        key = "delegated_tasks" if delegated else "active_tasks"
        lst = a.setdefault(key, [])
        if not isinstance(lst, list):
            a[key] = []
            lst = a[key]
        if task_id not in lst:
            lst.append(task_id)
        return


def set_agent_execution_state(st: dict[str, Any], agent_id: str, state: str) -> None:
    agents = st.get("agents")
    if not isinstance(agents, list):
        return
    for a in agents:
        if isinstance(a, dict) and str(a.get("id")) == agent_id:
            a["execution_state"] = state
            return
