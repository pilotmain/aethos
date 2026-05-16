# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.agents.agent_assignment_policy import assign_task_with_coordination_policy
from app.agents.agent_runtime import register_coordination_agent
from app.orchestration import task_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state


def test_agent_assignment_preserves_integrity(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    register_coordination_agent(st, user_id="u1", agent_type="operator")
    tid = task_registry.put_task(st, {"type": "workflow", "user_id": "u1", "state": "queued"})
    res = assign_task_with_coordination_policy(st, tid, user_id="u1")
    assert res.get("ok") is True
    assert validate_runtime_state(st).get("ok") is True
