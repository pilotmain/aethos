# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.orchestration import task_queue
from app.orchestration import task_registry
from app.orchestration import task_recovery
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_queues_survive_restart_and_recovery_requeues(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    tid = task_registry.put_task(st, {"type": "noop", "state": "running"})
    task_queue.enqueue_task_id(st, "execution_queue", "ghost-id")
    task_queue.enqueue_task_id(st, "deployment_queue", tid)
    save_runtime_state(st)

    st2 = load_runtime_state()
    rec = task_recovery.recover_orchestration_on_boot(st2)
    assert rec["count"] >= 1
    assert task_registry.get_task(st2, tid)["state"] == "recovering"
    assert tid in (st2.get("recovery_queue") or [])

    pruned = task_queue.prune_orphan_queue_entries(st2)
    assert pruned >= 1
    assert "ghost-id" not in (st2.get("execution_queue") or [])
