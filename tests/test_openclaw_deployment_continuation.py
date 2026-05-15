# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.workflow_runner import persist_operator_workflow
from app.orchestration import runtime_dispatcher
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_deploy_workflow_step_records_and_completes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    out = persist_operator_workflow(st, "deploy", user_id="dep_u")
    save_runtime_state(st)
    tid = out["task_id"]
    st2 = load_runtime_state()
    for _ in range(15):
        runtime_dispatcher.dispatch_once(st2)
        save_runtime_state(st2)
        t = task_registry.get_task(st2, tid)
        if t and str(t.get("state") or "") in ("completed", "failed"):
            break
    t3 = task_registry.get_task(load_runtime_state(), tid)
    assert t3 and t3.get("state") == "completed"
    stf = load_runtime_state()
    pid = str(t3.get("execution_plan_id") or "")
    assert pid
    from app.deployments.deployment_runtime import deployment_id_for_plan

    did = deployment_id_for_plan(pid)
    dep = (stf.get("deployment_records") or {}).get(did)
    assert isinstance(dep, dict)
    assert dep.get("status") == "completed"
