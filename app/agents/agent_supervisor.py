# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime supervisor rows (loop monitors / restart counters)."""

from __future__ import annotations

import uuid
from typing import Any

from app.agents import agent_events
from app.orchestration import orchestration_log
from app.runtime.runtime_state import utc_now_iso


def supervisors_map(st: dict[str, Any]) -> dict[str, Any]:
    s = st.setdefault("runtime_supervisors", {})
    if not isinstance(s, dict):
        st["runtime_supervisors"] = {}
        return st["runtime_supervisors"]
    return s


def ensure_supervisor(st: dict[str, Any], *, loop_type: str, user_id: str = "") -> dict[str, Any]:
    for _sid, row in supervisors_map(st).items():
        if isinstance(row, dict) and str(row.get("loop_type")) == str(loop_type):
            return row
    sid = f"sup_{uuid.uuid4().hex[:10]}"
    ts = utc_now_iso()
    rec: dict[str, Any] = {
        "supervisor_id": sid,
        "loop_type": str(loop_type),
        "status": "running",
        "user_id": str(user_id),
        "restarts": 0,
        "created_at": ts,
        "updated_at": ts,
    }
    supervisors_map(st)[sid] = rec
    return rec


def restart_supervisor(st: dict[str, Any], supervisor_id: str) -> dict[str, Any] | None:
    row = supervisors_map(st).get(str(supervisor_id))
    if not isinstance(row, dict):
        return None
    n = int(row.get("restarts") or 0) + 1
    row["restarts"] = n
    row["updated_at"] = utc_now_iso()
    supervisors_map(st)[str(supervisor_id)] = row
    m = st.setdefault("runtime_metrics", {})
    if isinstance(m, dict):
        m["coordination_supervisor_restarts"] = int(m.get("coordination_supervisor_restarts") or 0) + 1
    agent_events.emit_agent_event(
        st, "supervisor_restart", supervisor_id=supervisor_id, loop_type=row.get("loop_type"), restarts=n
    )
    orchestration_log.append_json_log(
        "agent_supervisor",
        "supervisor_restart",
        supervisor_id=supervisor_id,
        restarts=n,
    )
    return row
