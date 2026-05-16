# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.deployments.deployment_registry import upsert_deployment
from app.environments import environment_locks
from app.environments import environment_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state


@pytest.mark.edge_cases
def test_repeated_lock_repair_cycles(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    environment_registry.ensure_environment(st, "env_lkr", user_id="u1")
    upsert_deployment(
        st,
        "dpl_lkr",
        {
            "deployment_id": "dpl_lkr",
            "environment_id": "env_lkr",
            "user_id": "u1",
            "status": "completed",
            "deployment_stage": "completed",
        },
    )
    assert environment_locks.acquire_lock(st, "env_lkr", "dpl_lkr", user_id="u1")
    for _ in range(20):
        environment_locks.repair_stale_locks(st)
    assert validate_runtime_state(st).get("ok") is True
