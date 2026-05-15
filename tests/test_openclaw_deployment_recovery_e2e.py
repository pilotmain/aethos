# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.deployments.deployment_recovery import recover_deployments_on_boot
from app.deployments.deployment_registry import upsert_deployment
from app.environments import environment_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_boot_marks_running_as_recovering(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    environment_registry.ensure_environment(st, "env_x", user_id="u1")
    upsert_deployment(
        st,
        "dpl_test1",
        {
            "deployment_id": "dpl_test1",
            "environment_id": "env_x",
            "status": "running",
            "user_id": "u1",
            "workflow_id": "wf",
            "task_id": "",
            "created_logged": True,
        },
    )
    save_runtime_state(st)
    st2 = load_runtime_state()
    out = recover_deployments_on_boot(st2)
    assert out.get("deployments_marked_recovering") == 1
    row = (st2.get("deployment_records") or {}).get("dpl_test1")
    assert row and row.get("status") == "recovering"


def test_boot_marks_rollback_running_as_recovering(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    environment_registry.ensure_environment(st, "env_rb2", user_id="u1")
    upsert_deployment(
        st,
        "dpl_rb2",
        {
            "deployment_id": "dpl_rb2",
            "environment_id": "env_rb2",
            "status": "running",
            "user_id": "u1",
            "workflow_id": "wf",
            "task_id": "",
            "created_logged": True,
            "rollback": {"status": "running", "stage": "rolling_back"},
        },
    )
    save_runtime_state(st)
    st2 = load_runtime_state()
    out = recover_deployments_on_boot(st2)
    assert int(out.get("rollback_recoveries") or 0) == 1
    row = (st2.get("deployment_records") or {}).get("dpl_rb2")
    assert row and str((row.get("rollback") or {}).get("status")) == "recovering"
