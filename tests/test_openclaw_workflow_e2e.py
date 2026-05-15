# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.workflow_runner import persist_operator_workflow
from app.execution import execution_plan
from app.orchestration import runtime_dispatcher
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_operator_workflow_e2e_shell_and_result(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    out = persist_operator_workflow(st, "echo e2e_marker", user_id="u_e2e")
    save_runtime_state(st)
    tid = out["task_id"]
    pid = out["plan_id"]
    st2 = load_runtime_state()
    for _ in range(25):
        runtime_dispatcher.dispatch_once(st2)
        save_runtime_state(st2)
        t = task_registry.get_task(st2, tid)
        if t and str(t.get("state") or "") in ("completed", "failed"):
            break
    plan = execution_plan.get_plan(load_runtime_state(), pid)
    assert plan
    stdout = str((plan["steps"][0].get("result") or {}).get("stdout") or "")
    assert "e2e_marker" in stdout
