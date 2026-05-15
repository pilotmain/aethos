# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.agents.agent_coordination import assign_task_to_agent, list_tasks_for_agent
from app.agents.agent_runtime import register_coordination_agent
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state


def test_assign_task_updates_registry_and_agent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    tid = task_registry.put_task(
        st,
        {"type": "workflow", "user_id": "u1", "state": "queued", "agent_id": "wf"},
    )
    aid, _ = register_coordination_agent(st, user_id="u1", owner_session_id="")
    assign_task_to_agent(st, aid, tid)
    tasks = list_tasks_for_agent(st, aid, "u1")
    assert any(x["task_id"] == tid for x in tasks)
