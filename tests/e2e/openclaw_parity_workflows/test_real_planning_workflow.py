# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Benchmark: planning rows + decomposition alignment with workflow builder."""

from __future__ import annotations

from app.execution.workflow_runner import persist_operator_workflow
from app.planning.dependency_planner import add_linear_dependencies
from app.planning.plan_optimizer import optimize_planning_record
from app.planning.planner_runtime import planning_records
from app.planning.reasoning_runtime import append_reasoning
from app.planning.task_decomposition import decompose_operator_text
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from .support import configure_isolated_runtime, dispatch_until_task_terminal


def test_planning_record_tracks_operator_plan(tmp_path, monkeypatch) -> None:
    configure_isolated_runtime(monkeypatch, tmp_path)
    text = "create a file in workspace and summarize it"
    steps = decompose_operator_text(text)
    assert len(steps) >= 2
    steps2 = add_linear_dependencies(steps)
    assert steps2[1].get("depends_on")

    st = load_runtime_state()
    out = persist_operator_workflow(st, text, user_id="bench_plan")
    pid = str(out["plan_id"])
    save_runtime_state(st)

    st2 = load_runtime_state()
    plnid = None
    for plid, row in planning_records(st2).items():
        if isinstance(row, dict) and str(row.get("plan_id") or "") == pid:
            plnid = str(plid)
            break
    assert plnid

    optimize_planning_record(st2, plnid)
    append_reasoning(st2, plnid, "deterministic planner probe", kind="bench")
    save_runtime_state(st2)

    tid = str(out["task_id"])
    st3 = load_runtime_state()
    assert dispatch_until_task_terminal(st3, tid) == "completed"

    row = planning_records(load_runtime_state()).get(plnid) or {}
    assert isinstance(row.get("optimization_state"), dict)
    notes = ((row.get("reasoning_state") or {}).get("notes") or [])
    assert isinstance(notes, list) and len(notes) >= 1
