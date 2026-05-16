# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.agents.agent_assignment_policy import assign_task_with_coordination_policy
from app.agents.agent_runtime import register_coordination_agent
from app.orchestration import task_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_repeated_reassignment_stable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    register_coordination_agent(st, user_id="u1", agent_type="operator")
    for _ in range(10):
        tid = task_registry.put_task(st, {"type": "workflow", "user_id": "u1", "state": "queued"})
        r = assign_task_with_coordination_policy(st, tid, user_id="u1", agent_type="operator")
        assert r.get("ok") is True
    save_runtime_state(st)
    assert validate_runtime_state(load_runtime_state()).get("ok") is True
