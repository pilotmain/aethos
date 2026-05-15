# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Benchmark: interrupted running step → boot recovery → workflow completes."""

from __future__ import annotations

from app.execution import execution_plan
from app.execution.execution_continuation import recover_execution_on_boot
from app.execution.workflow_runner import persist_operator_workflow
from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from .support import configure_isolated_runtime, dispatch_until_task_terminal


def test_recover_running_shell_step_then_finish(tmp_path, monkeypatch) -> None:
    configure_isolated_runtime(monkeypatch, tmp_path)
    st = load_runtime_state()
    out = persist_operator_workflow(st, "echo recovery_after_interrupt", user_id="bench_rec")
    tid, pid = str(out["task_id"]), str(out["plan_id"])
    save_runtime_state(st)

    st1 = load_runtime_state()
    q = [x for x in (st1.get("execution_queue") or []) if str(x) != tid]
    st1["execution_queue"] = q
    plan = execution_plan.get_plan(st1, pid)
    assert plan and plan.get("steps")
    st1["execution"]["plans"][pid]["steps"][0]["status"] = "running"
    save_runtime_state(st1)

    st2 = load_runtime_state()
    rec = recover_execution_on_boot(st2)
    assert rec.get("count", 0) >= 1
    assert str(st2["execution"]["plans"][pid]["steps"][0].get("status") or "") == "queued"

    task_queue.enqueue_task_id(st2, "execution_queue", tid)
    save_runtime_state(st2)

    st3 = load_runtime_state()
    assert dispatch_until_task_terminal(st3, tid) == "completed"
    assert task_registry.get_task(load_runtime_state(), tid).get("state") == "completed"
    stdout = str((execution_plan.get_plan(load_runtime_state(), pid)["steps"][0].get("result") or {}).get("stdout") or "")
    assert "recovery_after_interrupt" in stdout
