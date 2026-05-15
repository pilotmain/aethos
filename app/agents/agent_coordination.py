# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Task ↔ agent ownership helpers."""

from __future__ import annotations

from typing import Any

from app.agents.agent_registry import get_agent, upsert_agent
from app.orchestration import task_registry


def assign_task_to_agent(st: dict[str, Any], agent_id: str, task_id: str) -> None:
    t = task_registry.get_task(st, task_id)
    if not t:
        return
    cur = str(t.get("state") or "queued")
    task_registry.update_task_state(st, task_id, cur, assigned_coordination_agent_id=str(agent_id))
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
