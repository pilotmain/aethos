# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Register coordination agents and heartbeats."""

from __future__ import annotations

import uuid
from typing import Any

from app.agents import agent_events
from app.agents.agent_registry import get_agent, upsert_agent
from app.runtime.runtime_state import utc_now_iso


def register_coordination_agent(
    st: dict[str, Any],
    *,
    agent_type: str = "operator",
    user_id: str,
    owner_session_id: str | None = None,
    status: str = "idle",
) -> tuple[str, dict[str, Any]]:
    aid = f"agt_{uuid.uuid4().hex[:12]}"
    ts = utc_now_iso()
    row: dict[str, Any] = {
        "agent_id": aid,
        "agent_type": str(agent_type)[:64],
        "status": str(status)[:32],
        "coordination_health": "healthy",
        "owner_session_id": str(owner_session_id or ""),
        "user_id": str(user_id),
        "active_tasks": [],
        "delegated_tasks": [],
        "created_at": ts,
        "last_heartbeat": ts,
        "execution_state": "active",
        "supervisor_state": {},
    }
    upsert_agent(st, aid, row)
    m = st.setdefault("runtime_metrics", {})
    if isinstance(m, dict):
        m["coordination_active_agents"] = len(
            [x for x in (st.get("coordination_agents") or {}).values() if isinstance(x, dict)]
        )
    agent_events.emit_agent_event(
        st, "agent_registered", agent_id=aid, user_id=user_id, agent_type=agent_type, status=status
    )
    agent_events.emit_agent_event(st, "agent_started", agent_id=aid, user_id=user_id, status=status)
    return aid, row


def heartbeat(st: dict[str, Any], agent_id: str) -> None:
    upsert_agent(st, agent_id, {"last_heartbeat": utc_now_iso()})


def set_agent_status(st: dict[str, Any], agent_id: str, status: str) -> None:
    prev = get_agent(st, agent_id) or {}
    s = str(status)[:32]
    if s in ("failed", "offline"):
        from app.agents.agent_assignment_policy import reassign_tasks_from_unhealthy_coordination_agent

        reassign_tasks_from_unhealthy_coordination_agent(st, str(agent_id), reason=s)
    patch: dict[str, Any] = {"status": s, "last_heartbeat": utc_now_iso()}
    if s in ("failed", "offline"):
        patch["coordination_health"] = s
    upsert_agent(st, agent_id, patch)
    if s == "failed":
        agent_events.emit_agent_event(
            st,
            "agent_failed",
            agent_id=agent_id,
            user_id=str(prev.get("user_id") or ""),
        )
