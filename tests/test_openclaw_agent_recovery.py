# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.agents.agent_recovery import recover_agent_coordination_on_boot
from app.agents.agent_runtime import register_coordination_agent
from app.agents.agent_loops import ensure_loop
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_boot_marks_running_agent_recovering(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    aid, _ = register_coordination_agent(st, user_id="u1", status="running")
    from app.agents.agent_registry import upsert_agent

    upsert_agent(st, aid, {"status": "running"})
    ensure_loop(st, "runtime_supervisor", user_id="u1")
    save_runtime_state(st)
    st2 = load_runtime_state()
    out = recover_agent_coordination_on_boot(st2)
    assert out.get("agents_marked_recovering") == 1
    ag = (st2.get("coordination_agents") or {}).get(aid, {})
    assert ag.get("status") == "recovering"
    assert ag.get("coordination_health") == "recovering"
