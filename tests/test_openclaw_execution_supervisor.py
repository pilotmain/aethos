# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.execution_plan import attach_plan_to_task, create_plan
from app.execution.execution_supervisor import tick_planned_task
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state


def test_supervisor_completes_multi_step_plan(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    tid = task_registry.put_task(st, {"type": "noop", "state": "queued"})
    pid = create_plan(st, tid, [{"step_id": "x"}, {"step_id": "y"}])
    attach_plan_to_task(st, tid, pid)
    r1 = tick_planned_task(st, tid)
    r2 = tick_planned_task(st, tid)
    assert r1.get("terminal") == "running"
    assert r2.get("terminal") == "completed"
    assert task_registry.get_task(st, tid)["state"] == "completed"
