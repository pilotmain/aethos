# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.deployments.deployment_recovery import recover_deployments_on_boot
from app.deployments.deployment_registry import upsert_deployment
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_boot_marks_running_as_recovering(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    upsert_deployment(
        st,
        "dpl_test1",
        {
            "deployment_id": "dpl_test1",
            "environment_id": "env_x",
            "status": "running",
            "user_id": "u1",
            "workflow_id": "wf",
            "task_id": "t",
            "created_logged": True,
        },
    )
    save_runtime_state(st)
    st2 = load_runtime_state()
    out = recover_deployments_on_boot(st2)
    assert out.get("deployments_marked_recovering") == 1
    row = (st2.get("deployment_records") or {}).get("dpl_test1")
    assert row and row.get("status") == "recovering"
