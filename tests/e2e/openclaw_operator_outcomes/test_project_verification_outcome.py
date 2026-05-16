# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.workflow_runner import persist_operator_workflow
from app.orchestration import runtime_dispatcher
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state
from app.runtime.integrity.runtime_integrity import validate_runtime_state


def test_operator_workflow_reaches_terminal_with_valid_runtime(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    out = persist_operator_workflow(st, "write file oc_outcome.txt hello", user_id="oc_u")
    save_runtime_state(st)
    tid = out["task_id"]
    st2 = load_runtime_state()
    for _ in range(40):
        runtime_dispatcher.dispatch_once(st2)
        save_runtime_state(st2)
        t = task_registry.get_task(st2, tid)
        if t and str(t.get("state") or "") in ("completed", "failed"):
            break
    t = task_registry.get_task(st2, tid)
    assert t and str(t.get("state") or "") == "completed"
    inv = validate_runtime_state(st2)
    assert inv.get("ok") is True
