# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.orchestration import runtime_dispatcher
from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state


def test_dispatcher_prefers_recovery_queue_over_execution(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    ta = task_registry.put_task(st, {"type": "noop", "state": "queued"})
    tb = task_registry.put_task(st, {"type": "noop", "state": "queued"})
    task_queue.enqueue_task_id(st, "execution_queue", ta)
    task_queue.enqueue_task_id(st, "recovery_queue", tb)
    res = runtime_dispatcher.dispatch_once(st)
    assert res and res.get("task_id") == tb
    assert task_registry.get_task(st, tb)["state"] == "completed"
    assert task_registry.get_task(st, ta)["state"] == "queued"
