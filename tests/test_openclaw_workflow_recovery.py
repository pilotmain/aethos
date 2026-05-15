# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.execution_plan import attach_plan_to_task, create_plan, get_plan
from app.execution.workflow_recovery import recover_workflows_on_boot
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state


def test_workflow_recovery_resets_running_step(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    tid = task_registry.put_task(
        st,
        {"type": "workflow", "state": "running", "user_id": "u1", "execution_plan_id": None},
    )
    pid = create_plan(
        st,
        tid,
        [{"step_id": "s1", "type": "noop", "tool": {"name": "noop", "input": {}}}],
    )
    attach_plan_to_task(st, tid, pid)
    p = get_plan(st, pid)
    assert p
    p["steps"][0]["status"] = "running"
    recover_workflows_on_boot(st)
    assert p["steps"][0]["status"] == "queued"
