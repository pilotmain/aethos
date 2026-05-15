# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.workflow_runner import persist_operator_workflow
from app.orchestration import runtime_dispatcher
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_concurrent_workflow_enqueues_remain_stable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    ids: list[str] = []
    for i in range(5):
        out = persist_operator_workflow(st, f"echo load_{i}", user_id="load_u")
        ids.append(str(out["task_id"]))
    save_runtime_state(st)
    st2 = load_runtime_state()
    for _ in range(80):
        runtime_dispatcher.dispatch_once(st2)
        save_runtime_state(st2)
        done = sum(
            1
            for tid in ids
            if (task_registry.get_task(st2, tid) or {}).get("state") == "completed"
        )
        if done == len(ids):
            break
    st3 = load_runtime_state()
    assert all((task_registry.get_task(st3, tid) or {}).get("state") == "completed" for tid in ids)
