# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.agents.agent_runtime import register_coordination_agent
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_two_agents_persist(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    register_coordination_agent(st, user_id="same")
    register_coordination_agent(st, user_id="same")
    save_runtime_state(st)
    st2 = load_runtime_state()
    ca = st2.get("coordination_agents") or {}
    assert len(ca) >= 2
