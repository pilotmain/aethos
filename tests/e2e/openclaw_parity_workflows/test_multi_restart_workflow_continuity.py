# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Long-horizon continuity: workflow survives save/reload mid-dispatch (restart proxy)."""

from __future__ import annotations

from app.execution.workflow_runner import persist_operator_workflow
from app.orchestration import runtime_dispatcher
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from .support import configure_isolated_runtime, dispatch_until_task_terminal


def test_workflow_survives_runtime_reload_mid_dispatch(tmp_path, monkeypatch) -> None:
    configure_isolated_runtime(monkeypatch, tmp_path)
    st = load_runtime_state()
    out = persist_operator_workflow(st, "echo continuity_ok", user_id="u_mrestart")
    tid = str(out["task_id"])
    save_runtime_state(st)

    st_mid = load_runtime_state()
    for _ in range(4):
        runtime_dispatcher.dispatch_once(st_mid)
        save_runtime_state(st_mid)

    st_after = load_runtime_state()
    t = task_registry.get_task(st_after, tid)
    assert isinstance(t, dict)
    assert str(t.get("state") or "") not in ("failed", "cancelled")

    assert dispatch_until_task_terminal(st_after, tid) == "completed"
    save_runtime_state(st_after)
    t_final = task_registry.get_task(load_runtime_state(), tid)
    assert t_final and str(t_final.get("state") or "") == "completed"
