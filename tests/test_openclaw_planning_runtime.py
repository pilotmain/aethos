# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.workflow_runner import persist_operator_workflow
from app.planning.plan_optimizer import optimize_planning_record
from app.planning.planner_runtime import ensure_planning_record_for_plan, get_planning
from app.planning.reasoning_runtime import append_reasoning
from app.planning.replanning_runtime import on_plan_terminal_failure
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_planning_record_created_with_workflow(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    out = persist_operator_workflow(st, "echo planning_row_ok", user_id="u_plan_wf")
    save_runtime_state(st)
    pid = str(out["plan_id"])
    st2 = load_runtime_state()
    pr = st2.get("planning_records") or {}
    found = None
    for row in pr.values():
        if isinstance(row, dict) and str(row.get("plan_id") or "") == pid:
            found = row
            break
    assert found is not None
    assert str(found.get("task_id") or "") == str(out["task_id"])
    assert str(found.get("user_id") or "") == "u_plan_wf"


def test_optimize_reasoning_replanning_mutations(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    plnid = ensure_planning_record_for_plan(st, task_id="t_unit", plan_id="p_unit", user_id="u_unit")
    optimize_planning_record(st, plnid)
    append_reasoning(st, plnid, "probe note", kind="test")
    on_plan_terminal_failure(st, task_id="t_unit", plan_id="p_unit", reason="unit_fail")
    m = st.get("runtime_metrics") or {}
    assert int(m.get("optimization_cycles_total") or 0) >= 1
    assert int(m.get("reasoning_cycles_total") or 0) >= 1
    assert int(m.get("replanning_total") or 0) >= 1
    row = get_planning(st, plnid)
    assert row and str(row.get("status") or "") == "replanning"


def test_integrity_flags_orphan_planning_plan(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    st.setdefault("planning_records", {})["pln_bad"] = {
        "planning_id": "pln_bad",
        "task_id": "no_such_task",
        "plan_id": "no_such_plan",
        "user_id": "u1",
        "reasoning_state": {"notes": []},
        "execution_strategy": {},
        "optimization_state": {},
        "recovery_plan": {},
        "delegation_plan": {},
    }
    inv = validate_runtime_state(st)
    assert inv.get("ok") is False
    issues = " ".join(inv.get("issues") or [])
    assert "planning_orphan_task" in issues
    assert "planning_orphan_plan" in issues
