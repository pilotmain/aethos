# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Interrupted workflow recovery (boot normalizes running → queued)."""

from __future__ import annotations

from app.execution.execution_continuation import recover_execution_on_boot
from app.execution.execution_plan import attach_plan_to_task, create_plan
from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_recover_execution_on_boot_resets_running_step(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    tid = task_registry.put_task(st, {"type": "workflow", "user_id": "u1", "state": "queued"})
    pid = create_plan(st, tid, [{"step_id": "s1", "type": "noop", "tool": {"name": "noop", "input": {}}}])
    attach_plan_to_task(st, tid, pid)
    st["execution"]["plans"][pid]["steps"][0]["status"] = "running"
    save_runtime_state(st)
    st2 = load_runtime_state()
    recover_execution_on_boot(st2)
    assert str(st2["execution"]["plans"][pid]["steps"][0].get("status") or "") == "queued"
    task_queue.enqueue_task_id(st2, "execution_queue", tid)
    save_runtime_state(st2)
