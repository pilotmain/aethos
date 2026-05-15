# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Benchmark: deploy intent → deployment record + terminal sync."""

from __future__ import annotations

from app.deployments.deployment_registry import get_deployment
from app.deployments.deployment_runtime import deployment_id_for_plan
from app.execution import execution_plan
from app.execution.workflow_runner import persist_operator_workflow
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from .support import configure_isolated_runtime, dispatch_until_task_terminal


def test_deploy_this_app_records_and_completes(tmp_path, monkeypatch) -> None:
    configure_isolated_runtime(monkeypatch, tmp_path)
    st = load_runtime_state()
    out = persist_operator_workflow(st, "deploy this app", user_id="bench_deploy")
    tid, pid = str(out["task_id"]), str(out["plan_id"])
    save_runtime_state(st)

    did = deployment_id_for_plan(pid)
    row0 = get_deployment(load_runtime_state(), did)
    assert row0 and row0.get("deployment_id") == did

    st2 = load_runtime_state()
    assert dispatch_until_task_terminal(st2, tid) == "completed"

    plan = execution_plan.get_plan(load_runtime_state(), pid)
    assert plan and str(plan.get("status") or "") == "completed"
    dep = get_deployment(load_runtime_state(), did)
    assert dep and str(dep.get("status") or "") == "completed"
