# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.deployments import deployment_rollback
from app.deployments.deployment_registry import get_deployment, upsert_deployment
from app.environments import environment_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from tests.parity_freeze_gate import repeated_cycles, widen_runtime_event_buffer


@pytest.mark.production_like
def test_repeated_rollbacks_preserve_bounded_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    widen_runtime_event_buffer(monkeypatch)
    n = repeated_cycles(large=50)
    get_settings.cache_clear()
    try:
        st = load_runtime_state()
        environment_registry.ensure_environment(st, "env_rb_int", user_id="u1")
        for i in range(n):
            did = f"dpl_rb_int_{i}"
            upsert_deployment(
                st,
                did,
                {
                    "deployment_id": did,
                    "environment_id": "env_rb_int",
                    "user_id": "u1",
                    "status": "completed",
                    "deployment_stage": "completed",
                    "rollback_available": True,
                    "task_id": "",
                    "checkpoints": [{"checkpoint_id": f"cp_keep_{i}", "deployment_id": did, "stage": "completed"}],
                },
            )
            assert deployment_rollback.start_rollback(st, did, reason="integrity_cycle")
            deployment_rollback.complete_rollback(st, did, success=True)
            row = get_deployment(st, did)
            assert row
            rb = row.get("rollback")
            assert isinstance(rb, dict)
            assert str(rb.get("status") or "") == "completed"
            logs = rb.get("logs")
            assert isinstance(logs, list) and len(logs) <= 500
            cps = row.get("checkpoints")
            assert isinstance(cps, list) and len(cps) <= 120
        save_runtime_state(st)
        assert validate_runtime_state(load_runtime_state()).get("ok") is True
    finally:
        get_settings.cache_clear()
