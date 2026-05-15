# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.execution_dependencies import ready_steps, validate_plan_dependency_dag
from app.execution.execution_plan import attach_plan_to_task, create_plan, get_plan
from app.execution.execution_supervisor import tick_planned_task
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state


def test_dependency_order_blocks_then_runs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    tid = task_registry.put_task(st, {"type": "noop", "state": "queued"})
    pid = create_plan(
        st,
        tid,
        [
            {"step_id": "a", "depends_on": []},
            {"step_id": "b", "depends_on": ["a"]},
        ],
    )
    attach_plan_to_task(st, tid, pid)
    p = get_plan(st, pid)
    assert ready_steps(p) and ready_steps(p)[0]["step_id"] == "a"
    tick_planned_task(st, tid)
    p2 = get_plan(st, pid)
    assert ready_steps(p2)[0]["step_id"] == "b"
    tick_planned_task(st, tid)
    p3 = get_plan(st, pid)
    assert not ready_steps(p3)


def test_validate_rejects_dependency_cycle(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    pid = create_plan(
        st,
        "x",
        [
            {"step_id": "a", "depends_on": ["b"]},
            {"step_id": "b", "depends_on": ["a"]},
        ],
    )
    p = get_plan(st, pid)
    assert not validate_plan_dependency_dag(p)
