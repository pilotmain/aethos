# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.deployments.deployment_registry import get_deployment
from app.deployments.deployment_runtime import deployment_id_for_plan, on_operator_plan_created_if_deploy
from app.execution import execution_plan
from app.execution.workflow_builder import build_steps_from_operator_text
from app.execution.workflow_runner import persist_operator_workflow
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_on_operator_plan_registers_deployment(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    steps = build_steps_from_operator_text("deploy")
    pid = execution_plan.create_plan(st, "t_x", steps)
    did = on_operator_plan_created_if_deploy(
        st, task_id="t_x", plan_id=str(pid), user_id="u1", session_id="s1", steps=steps
    )
    assert did == deployment_id_for_plan(str(pid))
    row = get_deployment(st, str(did))
    assert row and row.get("user_id") == "u1"
    save_runtime_state(st)


def test_persist_workflow_deploy_registers_via_runner(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    out = persist_operator_workflow(st, "deploy", user_id="u2")
    pid = str(out["plan_id"])
    did = deployment_id_for_plan(pid)
    row = get_deployment(st, did)
    assert row and row.get("workflow_id") == pid
