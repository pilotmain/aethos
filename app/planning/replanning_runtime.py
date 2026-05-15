# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Failure-aware replanning hints (persistent; does not mutate execution DAG automatically)."""

from __future__ import annotations

from typing import Any

from app.planning import planning_events
from app.planning.planner_runtime import get_planning, outcomes_list, planning_records
from app.runtime.runtime_state import utc_now_iso


def find_planning_id_for_plan(st: dict[str, Any], plan_id: str) -> str | None:
    pid = str(plan_id)
    for plnid, row in planning_records(st).items():
        if isinstance(row, dict) and str(row.get("plan_id") or "") == pid:
            return str(plnid)
    return None


def on_plan_terminal_failure(st: dict[str, Any], *, task_id: str, plan_id: str, reason: str) -> None:
    plnid = find_planning_id_for_plan(st, plan_id)
    if not plnid:
        return
    row = get_planning(st, plnid)
    if not row:
        return
    ts = utc_now_iso()
    rp = dict(row.get("recovery_plan") or {})
    rp["last_failure"] = {"ts": ts, "reason": (reason or "")[:2000], "task_id": str(task_id)}
    row["recovery_plan"] = rp
    row["status"] = "replanning"
    row["updated_at"] = ts
    planning_records(st)[plnid] = row
    m = st.setdefault("runtime_metrics", {})
    if isinstance(m, dict):
        m["replanning_total"] = int(m.get("replanning_total") or 0) + 1
    planning_events.emit_planning_event(
        st, "workflow_replanned", planning_id=plnid, task_id=str(task_id), plan_id=str(plan_id), reason=reason[:500]
    )
    snap = {"ts": ts, "planning_id": plnid, "event": "workflow_replanned", "task_id": str(task_id)}
    ol = outcomes_list(st)
    ol.append(snap)
    if len(ol) > 200:
        ol[:] = ol[-200:]
def on_adaptive_retry(st: dict[str, Any], *, task_id: str, plan_id: str, step_id: str, reason: str) -> None:
    plnid = find_planning_id_for_plan(st, plan_id)
    m = st.setdefault("runtime_metrics", {})
    if isinstance(m, dict):
        m["adaptive_retry_total"] = int(m.get("adaptive_retry_total") or 0) + 1
    planning_events.emit_planning_event(
        st,
        "adaptive_retry_triggered",
        planning_id=plnid or "",
        task_id=str(task_id),
        plan_id=str(plan_id),
        step_id=str(step_id),
        reason=(reason or "")[:500],
    )
    if plnid:
        row = get_planning(st, plnid)
        if row:
            rp = dict(row.get("recovery_plan") or {})
            retries = list(rp.get("adaptive_retries") or [])
            retries.append({"step_id": step_id, "reason": reason[:500], "ts": utc_now_iso()})
            rp["adaptive_retries"] = retries[-80:]
            row["recovery_plan"] = rp
            planning_records(st)[plnid] = row
