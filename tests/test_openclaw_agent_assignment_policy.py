# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.agents.agent_assignment_policy import (
    assign_task_with_coordination_policy,
    rank_coordination_agents_for_task,
)
from app.agents.agent_registry import upsert_agent
from app.agents.agent_runtime import register_coordination_agent, set_agent_status
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state


def test_rank_prefers_healthy_over_degraded(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    a_deg, _ = register_coordination_agent(st, user_id="u1", agent_type="operator")
    a_ok, _ = register_coordination_agent(st, user_id="u1", agent_type="operator")
    upsert_agent(st, a_deg, {"coordination_health": "degraded", "active_tasks": []})
    upsert_agent(st, a_ok, {"coordination_health": "healthy", "active_tasks": []})
    ranked = rank_coordination_agents_for_task(st, user_id="u1", agent_type="operator")
    assert ranked[0][0] == a_ok


def test_rank_prefers_less_loaded(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    heavy, _ = register_coordination_agent(st, user_id="u1", agent_type="operator")
    light, _ = register_coordination_agent(st, user_id="u1", agent_type="operator")
    upsert_agent(st, heavy, {"coordination_health": "healthy", "active_tasks": ["x1", "x2"]})
    upsert_agent(st, light, {"coordination_health": "healthy", "active_tasks": []})
    ranked = rank_coordination_agents_for_task(st, user_id="u1", agent_type="operator")
    assert ranked[0][0] == light


def test_policy_assign_persists_rationale(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    aid, _ = register_coordination_agent(st, user_id="u1", agent_type="operator")
    tid = task_registry.put_task(st, {"type": "workflow", "user_id": "u1", "state": "queued"})
    res = assign_task_with_coordination_policy(st, tid, user_id="u1", agent_type="operator")
    assert res.get("ok") is True
    assert res.get("agent_id") == aid
    row = task_registry.get_task(st, tid)
    assert isinstance(row, dict)
    ca = row.get("coordination_assignment")
    assert isinstance(ca, dict) and ca.get("policy_version") == "coordination_v1"


def test_failed_agent_reassigns_task(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    a1, _ = register_coordination_agent(st, user_id="u1", agent_type="operator")
    a2, _ = register_coordination_agent(st, user_id="u1", agent_type="operator")
    tid = task_registry.put_task(st, {"type": "workflow", "user_id": "u1", "state": "queued"})
    assign_task_with_coordination_policy(st, tid, user_id="u1", preferred_agent_id=a1)
    set_agent_status(st, a1, "failed")
    t2 = task_registry.get_task(st, tid)
    assert t2 and str(t2.get("assigned_coordination_agent_id") or "") == a2
    assert (st.get("coordination_agents") or {}).get(a2, {}).get("active_tasks")
