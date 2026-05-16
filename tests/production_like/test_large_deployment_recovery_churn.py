# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import os

import pytest

from app.deployments.deployment_recovery import recover_deployments_on_boot
from app.deployments.deployment_registry import upsert_deployment
from app.environments import environment_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


@pytest.mark.production_like
def test_large_deployment_recovery_churn(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    rounds = 20 if os.environ.get("AETHOS_CHURN_LARGE") == "1" else 9
    st = load_runtime_state()
    environment_registry.ensure_environment(st, "env_drc", user_id="u1")
    for _ in range(rounds):
        for j in range(6):
            upsert_deployment(
                st,
                f"dpl_drc_{j}",
                {
                    "deployment_id": f"dpl_drc_{j}",
                    "environment_id": "env_drc",
                    "user_id": "u1",
                    "status": "running",
                    "deployment_stage": "deploying",
                    "task_id": "",
                },
            )
        recover_deployments_on_boot(st)
    save_runtime_state(st)
    assert validate_runtime_state(load_runtime_state()).get("ok") is True
