# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Benchmark: coordination agents + delegations over real workflow tasks."""

from __future__ import annotations

from app.agents.agent_delegation import create_delegation, delegations_map
from app.agents.agent_runtime import register_coordination_agent
from app.execution.workflow_runner import persist_operator_workflow
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from .support import configure_isolated_runtime, dispatch_until_task_terminal


def test_delegate_verification_and_deployment_tasks(tmp_path, monkeypatch) -> None:
    configure_isolated_runtime(monkeypatch, tmp_path)
    st = load_runtime_state()
    parent_id, _ = register_coordination_agent(st, user_id="bench_ma")
    child_id, _ = register_coordination_agent(st, user_id="bench_ma")
    save_runtime_state(st)

    st = load_runtime_state()
    out_v = persist_operator_workflow(st, "run project verification", user_id="bench_ma")
    out_d = persist_operator_workflow(st, "deploy this app", user_id="bench_ma")
    tid_v, tid_d = str(out_v["task_id"]), str(out_d["task_id"])
    create_delegation(
        st,
        parent_agent_id=parent_id,
        child_agent_id=child_id,
        task_id=tid_v,
        user_id="bench_ma",
    )
    create_delegation(
        st,
        parent_agent_id=parent_id,
        child_agent_id=child_id,
        task_id=tid_d,
        user_id="bench_ma",
    )
    save_runtime_state(st)

    st2 = load_runtime_state()
    assert dispatch_until_task_terminal(st2, tid_v) == "completed"
    st3 = load_runtime_state()
    assert dispatch_until_task_terminal(st3, tid_d) == "completed"

    dm = delegations_map(load_runtime_state())
    assert len(dm) >= 2
