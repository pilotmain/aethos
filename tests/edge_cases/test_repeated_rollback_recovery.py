# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.deployments import deployment_rollback
from app.deployments.deployment_recovery import recover_deployments_on_boot
from app.deployments.deployment_registry import upsert_deployment
from app.environments import environment_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from tests.parity_freeze_gate import repeated_cycles, widen_runtime_event_buffer


@pytest.mark.edge_cases
def test_repeated_rollback_and_boot_recovery(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    widen_runtime_event_buffer(monkeypatch)
    get_settings.cache_clear()
    try:
        st = load_runtime_state()
        environment_registry.ensure_environment(st, "env_rb2", user_id="u1")
        for i in range(repeated_cycles(large=45)):
            did = f"dpl_rb2_{i}"
            upsert_deployment(
                st,
                did,
                {
                    "deployment_id": did,
                    "environment_id": "env_rb2",
                    "user_id": "u1",
                    "status": "completed",
                    "deployment_stage": "completed",
                    "rollback_available": True,
                    "task_id": "",
                },
            )
            assert deployment_rollback.start_rollback(st, did, reason="edge")
            deployment_rollback.complete_rollback(st, did, success=True)
            recover_deployments_on_boot(st)
        save_runtime_state(st)
        assert validate_runtime_state(load_runtime_state()).get("ok") is True
    finally:
        get_settings.cache_clear()
