# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Heuristic plan scoring + queue signals (deterministic; no LLM)."""

from __future__ import annotations

from typing import Any

from app.execution import execution_plan
from app.orchestration import task_queue
from app.planning import planning_events
from app.planning.planner_runtime import get_planning, planning_records
from app.runtime.runtime_state import utc_now_iso


def score_plan_steps(plan: dict[str, Any]) -> float:
    """Higher is better — penalize failed steps, reward completed."""
    steps = plan.get("steps") or []
    if not isinstance(steps, list) or not steps:
        return 0.0
    score = 0.0
    for s in steps:
        if not isinstance(s, dict):
            continue
        stt = str(s.get("status") or "")
        if stt == "completed":
            score += 1.0
        elif stt == "failed":
            score -= 2.0
        elif stt in ("running", "retrying"):
            score += 0.1
    return score


def optimize_planning_record(st: dict[str, Any], planning_id: str) -> dict[str, Any] | None:
    row = get_planning(st, planning_id)
    if not row:
        return None
    pid = str(row.get("plan_id") or "")
    plan = execution_plan.get_plan(st, pid) if pid else None
    sc = score_plan_steps(plan or {})
    opt = dict(row.get("optimization_state") or {})
    opt["last_score"] = sc
    opt["queue_snapshot"] = {qn: task_queue.queue_len(st, qn) for qn in task_queue.QUEUE_NAMES}
    row["optimization_state"] = opt
    row["updated_at"] = utc_now_iso()
    planning_records(st)[str(planning_id)] = row
    m = st.setdefault("runtime_metrics", {})
    if isinstance(m, dict):
        m["optimization_cycles_total"] = int(m.get("optimization_cycles_total") or 0) + 1
        if sc >= 0:
            m["optimization_success_total"] = int(m.get("optimization_success_total") or 0) + 1
    planning_events.emit_planning_event(st, "plan_optimized", planning_id=planning_id, plan_id=pid, score=sc)
    return row
