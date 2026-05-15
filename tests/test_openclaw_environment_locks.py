# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.deployments.deployment_registry import upsert_deployment
from app.environments import environment_locks
from app.environments import environment_registry
from app.runtime.runtime_state import load_runtime_state


def test_lock_blocks_second_deployment(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    environment_registry.ensure_environment(st, "env_lk", user_id="u1")
    assert environment_locks.acquire_lock(st, "env_lk", "dpl_a", user_id="u1")
    assert not environment_locks.acquire_lock(st, "env_lk", "dpl_b", user_id="u1")
    assert environment_locks.release_lock(st, "env_lk", "dpl_a")
    assert environment_locks.acquire_lock(st, "env_lk", "dpl_b", user_id="u1")


def test_repair_clears_lock_for_terminal_deployment(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    environment_registry.ensure_environment(st, "env_z", user_id="u1")
    upsert_deployment(
        st,
        "dpl_z",
        {
            "deployment_id": "dpl_z",
            "environment_id": "env_z",
            "user_id": "u1",
            "status": "completed",
            "deployment_stage": "completed",
        },
    )
    assert environment_locks.acquire_lock(st, "env_z", "dpl_z", user_id="u1")
    out = environment_locks.repair_stale_locks(st)
    assert int(out.get("locks_repaired") or 0) >= 1
    assert environment_locks.get_lock(st, "env_z") is None
