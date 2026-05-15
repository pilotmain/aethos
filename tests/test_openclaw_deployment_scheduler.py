# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.deployments.deployment_scheduler import acquire_environment_lock, enqueue_deployment, release_environment_lock
from app.runtime.runtime_state import load_runtime_state


def test_scheduler_queue_and_lock(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    enqueue_deployment(st, "d1", priority=1)
    enqueue_deployment(st, "d0", priority=2)
    root = st.get("deployment_scheduler") or {}
    pend = root.get("pending") or []
    assert pend[0].get("deployment_id") == "d0"
    assert acquire_environment_lock(st, "env_a", "holder1")
    assert not acquire_environment_lock(st, "env_a", "holder2")
    release_environment_lock(st, "env_a", "holder1")
    assert acquire_environment_lock(st, "env_a", "holder2")
