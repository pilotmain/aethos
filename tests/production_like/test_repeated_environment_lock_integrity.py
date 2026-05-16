# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.deployments.deployment_lifecycle import transition_deployment_stage
from app.deployments.deployment_registry import upsert_deployment
from app.environments import environment_locks
from app.environments import environment_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from tests.parity_freeze_gate import repeated_cycles, widen_runtime_event_buffer


@pytest.mark.production_like
def test_repeated_lock_acquire_release_keeps_maps_consistent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    widen_runtime_event_buffer(monkeypatch)
    n = repeated_cycles(large=44)
    get_settings.cache_clear()
    try:
        st = load_runtime_state()
        environment_registry.ensure_environment(st, "env_lk_int", user_id="u1")
        for i in range(n):
            did = f"dpl_lk_{i}"
            upsert_deployment(
                st,
                did,
                {
                    "deployment_id": did,
                    "environment_id": "env_lk_int",
                    "user_id": "u1",
                    "status": "running",
                    "deployment_stage": "deploying",
                    "task_id": "",
                },
            )
            assert environment_locks.acquire_lock(st, "env_lk_int", did, user_id="u1")
            lk = environment_locks.get_lock(st, "env_lk_int")
            assert lk and str(lk.get("locked_by_deployment_id") or "") == did
            transition_deployment_stage(st, did, "verifying", reason="lock_int", sync_status=True)
            transition_deployment_stage(st, did, "completed", reason="lock_int", sync_status=True)
            environment_locks.repair_stale_locks(st)
            assert environment_locks.get_lock(st, "env_lk_int") is None
        save_runtime_state(st)
        assert validate_runtime_state(load_runtime_state()).get("ok") is True
    finally:
        get_settings.cache_clear()
