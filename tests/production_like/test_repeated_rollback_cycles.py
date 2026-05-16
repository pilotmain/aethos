# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import os

import pytest

from app.deployments import deployment_rollback
from app.deployments.deployment_registry import upsert_deployment
from app.environments import environment_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


@pytest.mark.production_like
def test_many_rollback_complete_cycles(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    n = 18 if os.environ.get("AETHOS_CHURN_LARGE") == "1" else 8
    for i in range(n):
        st = load_runtime_state()
        environment_registry.ensure_environment(st, "env_prb", user_id="u1")
        did = f"dpl_prb_{i}"
        upsert_deployment(
            st,
            did,
            {
                "deployment_id": did,
                "environment_id": "env_prb",
                "user_id": "u1",
                "status": "completed",
                "deployment_stage": "completed",
                "rollback_available": True,
                "task_id": "",
            },
        )
        assert deployment_rollback.start_rollback(st, did, reason="prod_cycle")
        deployment_rollback.complete_rollback(st, did, success=True)
        save_runtime_state(st)
    assert validate_runtime_state(load_runtime_state()).get("ok") is True
