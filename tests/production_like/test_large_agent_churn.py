# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import os

import pytest

from app.agents.agent_assignment_policy import assign_task_with_coordination_policy
from app.agents.agent_runtime import register_coordination_agent
from app.orchestration import task_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


@pytest.mark.production_like
def test_large_agent_assignment_churn(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    n = 35 if os.environ.get("AETHOS_CHURN_LARGE") == "1" else 18
    st = load_runtime_state()
    register_coordination_agent(st, user_id="u1", agent_type="operator")
    for i in range(n):
        tid = task_registry.put_task(st, {"type": "workflow", "user_id": "u1", "state": "queued"})
        assign_task_with_coordination_policy(st, tid, user_id="u1", agent_type="operator")
    save_runtime_state(st)
    assert validate_runtime_state(load_runtime_state()).get("ok") is True
