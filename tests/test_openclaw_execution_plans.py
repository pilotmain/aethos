# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.execution_plan import attach_plan_to_task, create_plan, get_plan
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_execution_plan_persist_subtasks(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    from app.orchestration import task_registry

    tid = task_registry.put_task(st, {"type": "noop", "state": "queued"})
    pid = create_plan(
        st,
        tid,
        [{"step_id": "s1", "depends_on": []}, {"step_id": "s2", "depends_on": ["s1"]}],
    )
    attach_plan_to_task(st, tid, pid)
    save_runtime_state(st)
    st2 = load_runtime_state()
    p = get_plan(st2, pid)
    assert p and p["task_id"] == tid
    assert len(p["steps"]) == 2
    assert p["steps"][1]["depends_on"] == ["s1"]
