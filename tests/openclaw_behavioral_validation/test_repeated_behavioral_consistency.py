# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.workflow_runner import persist_operator_workflow
from app.orchestration import runtime_dispatcher
from app.orchestration import task_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_repeated_workflow_outcomes_consistent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    for i in range(4):
        st = load_runtime_state()
        out = persist_operator_workflow(st, f"write file rb_consist_{i}.txt body", user_id="rb_u")
        tid = out["task_id"]
        save_runtime_state(st)
        st2 = load_runtime_state()
        for _ in range(40):
            runtime_dispatcher.dispatch_once(st2)
            save_runtime_state(st2)
            if (task_registry.get_task(st2, tid) or {}).get("state") == "completed":
                break
        assert (task_registry.get_task(st2, tid) or {}).get("state") == "completed"
        assert validate_runtime_state(st2).get("ok") is True
