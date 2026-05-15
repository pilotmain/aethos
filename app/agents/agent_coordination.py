# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Task ↔ agent ownership helpers."""

from __future__ import annotations

from typing import Any

from app.agents.agent_registry import get_agent, upsert_agent
from app.orchestration import task_registry


def detach_task_from_coordination_agent(st: dict[str, Any], task_id: str) -> str | None:
    """Remove ``task_id`` from its agent's ``active_tasks`` and clear assignment on the task."""
    tid = str(task_id)
    t = task_registry.get_task(st, tid)
    if not isinstance(t, dict):
        return None
    aid = str(t.get("assigned_coordination_agent_id") or "").strip()
    if not aid:
        return None
    ag = get_agent(st, aid)
    if isinstance(ag, dict):
        active = [str(x) for x in (ag.get("active_tasks") or []) if str(x) != tid]
        upsert_agent(st, aid, {"active_tasks": active[-500:]})
    cur = str(t.get("state") or "queued")
    task_registry.update_task_state(st, tid, cur, assigned_coordination_agent_id="")
    return aid


def assign_task_to_agent(
    st: dict[str, Any],
    agent_id: str,
    task_id: str,
    *,
    coordination_assignment: dict[str, Any] | None = None,
) -> None:
    t = task_registry.get_task(st, task_id)
    if not t:
        return
    cur = str(t.get("state") or "queued")
    extra: dict[str, Any] = {"assigned_coordination_agent_id": str(agent_id)}
    if coordination_assignment is not None:
        extra["coordination_assignment"] = coordination_assignment
    task_registry.update_task_state(st, task_id, cur, **extra)
    ag = get_agent(st, agent_id)
    if ag:
        active = list(ag.get("active_tasks") or [])
        active.append(str(task_id))
        upsert_agent(st, agent_id, {"active_tasks": active[-500:], "status": "running"})


def list_tasks_for_agent(st: dict[str, Any], agent_id: str, app_user_id: str) -> list[dict[str, Any]]:
    uid = str(app_user_id or "").strip()
    out: list[dict[str, Any]] = []
    for tid, t in task_registry.registry(st).items():
        if not isinstance(t, dict):
            continue
        if str(t.get("assigned_coordination_agent_id") or "") != str(agent_id):
            continue
        if uid and str(t.get("user_id") or "") != uid:
            continue
        out.append({"task_id": str(tid), **{k: t.get(k) for k in ("state", "type", "execution_plan_id", "user_id")}})
    return out
