# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.workflow_runner import persist_operator_workflow
from app.orchestration import runtime_dispatcher
from app.orchestration import task_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_runtime_restart_continuity_outcome(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    out = persist_operator_workflow(st, "write file oc_restart.txt x", user_id="oc_rs")
    tid = out["task_id"]
    save_runtime_state(st)
    for round_i in range(3):
        stx = load_runtime_state()
        for _ in range(25):
            runtime_dispatcher.dispatch_once(stx)
            save_runtime_state(stx)
        assert validate_runtime_state(load_runtime_state()).get("ok") is True
    tf = task_registry.get_task(load_runtime_state(), tid)
    assert tf and str(tf.get("state") or "") == "completed"
