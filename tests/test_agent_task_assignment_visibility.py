# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.agent_work_state import (
    create_agent_task,
    find_runtime_agent_by_handle,
    link_registry_agent_to_runtime,
    list_tasks_for_agent,
)


def test_create_agent_task_tracked() -> None:
    row = link_registry_agent_to_runtime(registry_agent_id="r1", name="qa_helper", domain="qa")
    aid = str(row["agent_id"])
    tid = create_agent_task(
        runtime_agent_id=aid,
        agent_handle="qa_helper",
        prompt="research competitors",
        registry_agent_id="r1",
    )
    tasks = list_tasks_for_agent(aid)
    assert any(t.get("task_id") == tid for t in tasks)
    rt = find_runtime_agent_by_handle("qa_helper")
    assert rt.get("current_task_id") == tid or rt.get("status") == "busy"
