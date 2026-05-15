# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Benchmark: operator asks to run project verification (shell + persistence)."""

from __future__ import annotations

from app.execution import execution_checkpoint
from app.execution import execution_plan
from app.execution.workflow_runner import persist_operator_workflow
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from .support import configure_isolated_runtime, dispatch_until_task_terminal


def test_run_project_verification_shell_workflow(tmp_path, monkeypatch) -> None:
    configure_isolated_runtime(monkeypatch, tmp_path)
    st = load_runtime_state()
    out = persist_operator_workflow(st, "run project verification", user_id="bench_shell")
    tid, pid = str(out["task_id"]), str(out["plan_id"])
    save_runtime_state(st)

    assert int((st.get("runtime_metrics") or {}).get("planning_generated_total") or 0) >= 1
    buf = st.get("runtime_event_buffer")
    assert isinstance(buf, list) and len(buf) >= 1

    st2 = load_runtime_state()
    final = dispatch_until_task_terminal(st2, tid)
    assert final == "completed"

    plan = execution_plan.get_plan(load_runtime_state(), pid)
    assert plan and str(plan.get("status") or "") == "completed"
    step0 = plan["steps"][0]
    assert str(step0.get("type") or "") == "shell"
    cmd = str((step0.get("tool") or {}).get("input", {}).get("command") or "")
    assert "compileall" in cmd
    res = step0.get("result") or {}
    assert res.get("ok") is True
    rc = res.get("returncode")
    assert rc is not None and int(rc) == 0

    cp = execution_checkpoint.get_checkpoint(load_runtime_state(), pid, str(step0.get("step_id")))
    assert cp is not None
