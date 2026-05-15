# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Structured reasoning snippets attached to planning records."""

from __future__ import annotations

from typing import Any

from app.planning import planning_events
from app.planning.planner_runtime import get_planning, planning_records
from app.runtime.runtime_state import utc_now_iso


def append_reasoning(st: dict[str, Any], planning_id: str, note: str, *, kind: str = "note") -> dict[str, Any] | None:
    row = get_planning(st, planning_id)
    if not row:
        return None
    rs = dict(row.get("reasoning_state") or {})
    notes = list(rs.get("notes") or [])
    notes.append({"ts": utc_now_iso(), "kind": str(kind)[:64], "text": (note or "")[:4000]})
    rs["notes"] = notes[-200:]
    row["reasoning_state"] = rs
    row["updated_at"] = utc_now_iso()
    planning_records(st)[str(planning_id)] = row
    m = st.setdefault("runtime_metrics", {})
    if isinstance(m, dict):
        m["reasoning_cycles_total"] = int(m.get("reasoning_cycles_total") or 0) + 1
    planning_events.emit_planning_event(
        st, "reasoning_completed", planning_id=planning_id, kind=kind, preview=(note or "")[:200]
    )
    return row
