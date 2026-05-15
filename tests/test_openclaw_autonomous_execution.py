# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.execution_plan import attach_plan_to_task, create_plan
from app.orchestration import runtime_dispatcher
from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state


def test_autonomous_dispatcher_requeues_until_done(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    tid = task_registry.put_task(st, {"type": "noop", "state": "queued"})
    pid = create_plan(st, tid, [{"step_id": "1"}, {"step_id": "2"}])
    attach_plan_to_task(st, tid, pid)
    task_queue.enqueue_task_id(st, "execution_queue", tid)
    for _ in range(6):
        runtime_dispatcher.dispatch_once(st)
        t = task_registry.get_task(st, tid)
        if t and t.get("state") == "completed":
            break
    assert task_registry.get_task(st, tid)["state"] == "completed"
