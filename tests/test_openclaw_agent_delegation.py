# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.agents.agent_delegation import complete_delegation, create_delegation, list_delegations_for_agent
from app.agents.agent_runtime import register_coordination_agent
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state


def test_delegation_lifecycle(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    tid = task_registry.put_task(st, {"type": "workflow", "user_id": "u1", "state": "queued"})
    p, _ = register_coordination_agent(st, user_id="u1")
    c, _ = register_coordination_agent(st, user_id="u1")
    did = create_delegation(st, parent_agent_id=p, child_agent_id=c, task_id=tid, user_id="u1")
    assert list_delegations_for_agent(st, p)
    complete_delegation(st, did, success=True)
    row = (st.get("agent_delegations") or {}).get(did)
    assert row and row.get("status") == "completed"
