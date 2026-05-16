# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.deployments.deployment_registry import upsert_deployment
from app.environments import environment_locks
from app.environments import environment_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from tests.parity_freeze_gate import repeated_cycles


@pytest.mark.production_like
def test_many_lock_acquire_repair_cycles(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    n = repeated_cycles(large=55)
    st = load_runtime_state()
    environment_registry.ensure_environment(st, "env_elc", user_id="u1")
    upsert_deployment(
        st,
        "dpl_elc",
        {
            "deployment_id": "dpl_elc",
            "environment_id": "env_elc",
            "user_id": "u1",
            "status": "completed",
            "deployment_stage": "completed",
        },
    )
    for _ in range(n):
        environment_locks.acquire_lock(st, "env_elc", "dpl_elc", user_id="u1")
        environment_locks.repair_stale_locks(st)
    save_runtime_state(st)
    assert validate_runtime_state(load_runtime_state()).get("ok") is True
