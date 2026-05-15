# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.deployments.deployment_recovery import recover_deployments_on_boot
from app.deployments.deployment_registry import upsert_deployment
from app.environments import environment_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_deployment_boot_marks_running_recovering(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    environment_registry.ensure_environment(st, "env_r", user_id="u1")
    upsert_deployment(
        st,
        "dpl_res1",
        {
            "deployment_id": "dpl_res1",
            "environment_id": "env_r",
            "status": "running",
            "user_id": "u1",
            "workflow_id": "w",
            "task_id": "",
            "created_logged": True,
        },
    )
    save_runtime_state(st)
    st2 = load_runtime_state()
    out = recover_deployments_on_boot(st2)
    assert int(out.get("deployments_marked_recovering") or 0) >= 1
