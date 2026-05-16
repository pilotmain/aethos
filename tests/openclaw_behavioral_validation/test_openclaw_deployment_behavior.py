# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.deployments.deployment_registry import upsert_deployment
from app.deployments.deployment_lifecycle import transition_deployment_stage
from app.environments import environment_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state


def test_deployment_stage_transitions_keep_valid_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    environment_registry.ensure_environment(st, "env_bv", user_id="u1")
    upsert_deployment(
        st,
        "dpl_bv",
        {
            "deployment_id": "dpl_bv",
            "environment_id": "env_bv",
            "user_id": "u1",
            "status": "running",
            "deployment_stage": "building",
            "task_id": "",
        },
    )
    transition_deployment_stage(st, "dpl_bv", "deploying", reason="test", sync_status=True)
    inv = validate_runtime_state(st)
    assert inv.get("ok") is True
