# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.deployments.deployment_registry import upsert_deployment
from app.deployments.deployment_recovery import recover_deployments_on_boot
from app.environments import environment_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_multiple_deployments_recovery_stress(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    environment_registry.ensure_environment(st, "env_stress_d", user_id="u1")
    for i in range(12):
        upsert_deployment(
            st,
            f"dpl_st_{i}",
            {
                "deployment_id": f"dpl_st_{i}",
                "environment_id": "env_stress_d",
                "user_id": "u1",
                "status": "running",
                "deployment_stage": "deploying",
                "task_id": "",
            },
        )
    recover_deployments_on_boot(st)
    save_runtime_state(st)
    assert validate_runtime_state(load_runtime_state()).get("ok") is True
