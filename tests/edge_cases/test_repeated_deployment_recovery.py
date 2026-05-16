# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.deployments.deployment_recovery import recover_deployments_on_boot
from app.deployments.deployment_registry import upsert_deployment
from app.environments import environment_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


@pytest.mark.edge_cases
def test_repeated_deployment_recovery_cycles(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    for _ in range(15):
        st = load_runtime_state()
        environment_registry.ensure_environment(st, "env_ed", user_id="u1")
        upsert_deployment(
            st,
            "dpl_ed",
            {
                "deployment_id": "dpl_ed",
                "environment_id": "env_ed",
                "user_id": "u1",
                "status": "running",
                "deployment_stage": "deploying",
                "task_id": "",
            },
        )
        recover_deployments_on_boot(st)
        save_runtime_state(st)
    assert validate_runtime_state(load_runtime_state()).get("ok") is True
