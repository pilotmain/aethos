# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution import execution_plan
from app.execution.workflow_runner import persist_operator_workflow
from app.orchestration import runtime_dispatcher
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_workflow_persist_and_dispatch_echo(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    out = persist_operator_workflow(st, "echo wf_runner_ok", user_id="u1")
    save_runtime_state(st)
    tid = out["task_id"]
    st2 = load_runtime_state()
    for _ in range(20):
        runtime_dispatcher.dispatch_once(st2)
        save_runtime_state(st2)
        t = task_registry.get_task(st2, tid)
        if t and str(t.get("state") or "") in ("completed", "failed"):
            break
    t2 = task_registry.get_task(load_runtime_state(), tid)
    assert t2 and t2.get("state") == "completed"
    pid = str(t2.get("execution_plan_id") or "")
    plan = execution_plan.get_plan(load_runtime_state(), pid)
    assert plan
    res = (plan["steps"][0].get("result") or {})
    assert res.get("returncode") == 0
    assert res.get("ok") is True
