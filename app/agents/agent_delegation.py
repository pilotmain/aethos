# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Delegation records between coordination agents."""

from __future__ import annotations

import uuid
from typing import Any

from app.agents import agent_events
from app.agents.agent_registry import get_agent, upsert_agent
from app.runtime.runtime_state import utc_now_iso


def delegations_map(st: dict[str, Any]) -> dict[str, Any]:
    d = st.setdefault("agent_delegations", {})
    if not isinstance(d, dict):
        st["agent_delegations"] = {}
        return st["agent_delegations"]
    return d


def create_delegation(
    st: dict[str, Any],
    *,
    parent_agent_id: str,
    child_agent_id: str,
    task_id: str,
    user_id: str,
) -> str:
    did = f"dlg_{uuid.uuid4().hex[:12]}"
    ts = utc_now_iso()
    delegations_map(st)[did] = {
        "delegation_id": did,
        "parent_agent_id": str(parent_agent_id),
        "child_agent_id": str(child_agent_id),
        "task_id": str(task_id),
        "user_id": str(user_id),
        "status": "running",
        "created_at": ts,
        "updated_at": ts,
    }
    parent = get_agent(st, parent_agent_id)
    if parent:
        dt = list(parent.get("delegated_tasks") or [])
        dt.append(str(task_id))
        upsert_agent(st, parent_agent_id, {"delegated_tasks": dt[-200:], "status": "delegating"})
    m = st.setdefault("runtime_metrics", {})
    if isinstance(m, dict):
        m["coordination_delegations_total"] = int(m.get("coordination_delegations_total") or 0) + 1
    agent_events.emit_agent_event(
        st,
        "delegation_created",
        delegation_id=did,
        parent_agent_id=parent_agent_id,
        child_agent_id=child_agent_id,
        task_id=task_id,
        user_id=user_id,
    )
    return did


def complete_delegation(st: dict[str, Any], delegation_id: str, *, success: bool) -> None:
    row = delegations_map(st).get(str(delegation_id))
    if not isinstance(row, dict):
        return
    ts = utc_now_iso()
    row["status"] = "completed" if success else "failed"
    row["updated_at"] = ts
    delegations_map(st)[str(delegation_id)] = row
    agent_events.emit_agent_event(
        st,
        "delegation_completed",
        delegation_id=str(delegation_id),
        parent_agent_id=row.get("parent_agent_id"),
        child_agent_id=row.get("child_agent_id"),
        task_id=row.get("task_id"),
        status=row["status"],
    )


def list_delegations_for_agent(st: dict[str, Any], agent_id: str) -> list[dict[str, Any]]:
    aid = str(agent_id)
    out: list[dict[str, Any]] = []
    for _did, row in delegations_map(st).items():
        if not isinstance(row, dict):
            continue
        if str(row.get("parent_agent_id") or "") == aid or str(row.get("child_agent_id") or "") == aid:
            out.append(dict(row))
    return out
