# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Benchmark: create a workspace file and read it back (summarize = surface content)."""

from __future__ import annotations

from app.core.paths import get_aethos_workspace_root
from app.execution import execution_plan
from app.execution.workflow_runner import persist_operator_workflow
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from .support import configure_isolated_runtime, dispatch_until_task_terminal


def test_create_file_in_workspace_and_summarize(tmp_path, monkeypatch) -> None:
    configure_isolated_runtime(monkeypatch, tmp_path)
    st = load_runtime_state()
    out = persist_operator_workflow(
        st,
        "create a file in workspace and summarize it",
        user_id="bench_file",
    )
    tid, pid = str(out["task_id"]), str(out["plan_id"])
    save_runtime_state(st)

    st2 = load_runtime_state()
    final = dispatch_until_task_terminal(st2, tid)
    assert final == "completed"

    plan = execution_plan.get_plan(load_runtime_state(), pid)
    steps = plan.get("steps") or []
    assert len(steps) == 2
    read_step = steps[1]
    r = read_step.get("result") or {}
    assert r.get("ok") is True
    assert "parity benchmark workspace body" in str(r.get("content") or "")

    p = get_aethos_workspace_root() / ".parity_bench" / "summary_target.txt"
    assert p.is_file()
    assert "parity benchmark" in p.read_text(encoding="utf-8")
