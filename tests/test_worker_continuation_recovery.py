# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.orchestration.task_registry import put_task
from app.runtime.runtime_state import load_runtime_state, save_runtime_state
from app.runtime.worker_operational_memory import create_continuation, recover_worker_continuity


def test_recover_running_tasks() -> None:
    st = load_runtime_state()
    put_task(
        st,
        {
            "id": "t_rec",
            "state": "running",
            "assigned_agent_id": "agent_xyz",
        },
    )
    save_runtime_state(st)
    n = recover_worker_continuity()
    assert n >= 1
    st2 = load_runtime_state()
    conts = st2.get("worker_continuations") or {}
    assert any(isinstance(v, dict) for v in conts.values())
