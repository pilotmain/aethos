# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Autonomous supervision loop registry (background coordination)."""

from __future__ import annotations

import uuid
from typing import Any

from app.agents import agent_events
from app.runtime.runtime_state import utc_now_iso

LOOP_TYPES = frozenset(
    {
        "deployment_supervisor",
        "environment_supervisor",
        "retry_supervisor",
        "cleanup_supervisor",
        "runtime_supervisor",
        "workflow_supervisor",
    }
)


def loops_list(st: dict[str, Any]) -> list[Any]:
    lo = st.setdefault("autonomous_loops", [])
    if not isinstance(lo, list):
        st["autonomous_loops"] = []
        return st["autonomous_loops"]
    return lo


def ensure_loop(
    st: dict[str, Any],
    loop_type: str,
    *,
    owner_agent_id: str | None = None,
    user_id: str = "",
) -> dict[str, Any]:
    lt = str(loop_type or "").strip()
    if lt not in LOOP_TYPES:
        raise ValueError(f"unsupported loop type: {loop_type}")
    for row in loops_list(st):
        if isinstance(row, dict) and str(row.get("loop_type")) == lt and str(row.get("status")) in (
            "running",
            "waiting",
        ):
            return row
    lid = f"loop_{uuid.uuid4().hex[:10]}"
    ts = utc_now_iso()
    rec: dict[str, Any] = {
        "loop_id": lid,
        "loop_type": lt,
        "status": "running",
        "owner_agent_id": str(owner_agent_id or ""),
        "user_id": str(user_id),
        "created_at": ts,
        "updated_at": ts,
        "ticks": 0,
    }
    loops_list(st).append(rec)
    m = st.setdefault("runtime_metrics", {})
    if isinstance(m, dict):
        m["coordination_autonomous_loops"] = len([x for x in loops_list(st) if isinstance(x, dict)])
    agent_events.emit_agent_event(
        st, "loop_started", loop_id=lid, loop_type=lt, user_id=user_id, owner_agent_id=owner_agent_id or ""
    )
    return rec


def mark_loop_recovered(st: dict[str, Any], loop_id: str) -> None:
    for row in loops_list(st):
        if isinstance(row, dict) and str(row.get("loop_id")) == str(loop_id):
            row["status"] = "running"
            row["updated_at"] = utc_now_iso()
            agent_events.emit_agent_event(st, "loop_recovered", loop_id=loop_id, loop_type=row.get("loop_type"))
            m = st.setdefault("runtime_metrics", {})
            if isinstance(m, dict):
                m["coordination_recovery_loops"] = int(m.get("coordination_recovery_loops") or 0) + 1
            return
