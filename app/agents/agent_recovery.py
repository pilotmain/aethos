# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Recover coordination agents + autonomous loops after process restart."""

from __future__ import annotations

from typing import Any

from app.agents import agent_events
from app.agents.agent_loops import loops_list
from app.agents.agent_registry import agents_map, upsert_agent
from app.runtime.runtime_state import utc_now_iso


def recover_agent_coordination_on_boot(st: dict[str, Any]) -> dict[str, Any]:
    agents_n = loops_n = 0
    ts = utc_now_iso()
    for aid, row in list(agents_map(st).items()):
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "") in ("running", "delegating", "retrying"):
            upsert_agent(st, str(aid), {"status": "recovering", "coordination_health": "recovering", "last_heartbeat": ts})
            agent_events.emit_agent_event(
                st, "agent_recovered", agent_id=str(aid), user_id=str(row.get("user_id") or ""), status="recovering"
            )
            agents_n += 1
    for row in loops_list(st):
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "") == "running":
            row["status"] = "waiting"
            row["updated_at"] = ts
            agent_events.emit_agent_event(
                st, "loop_recovered", loop_id=str(row.get("loop_id")), loop_type=row.get("loop_type")
            )
            loops_n += 1
    return {"agents_marked_recovering": agents_n, "loops_marked_waiting": loops_n}
