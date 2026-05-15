# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.orchestration import agent_runtime
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_agent_runtime_persists_task_binding(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    aid = agent_runtime.register_agent(st, {"name": "test-agent"})
    tid = task_registry.put_task(st, {"type": "noop", "state": "queued", "agent_id": aid})
    agent_runtime.attach_task_to_agent(st, aid, tid, delegated=False)
    agent_runtime.attach_task_to_agent(st, aid, tid, delegated=True)
    save_runtime_state(st)
    st2 = load_runtime_state()
    agents = st2.get("agents") or []
    row = next((a for a in agents if isinstance(a, dict) and str(a.get("id")) == aid), None)
    assert row is not None
    assert tid in (row.get("active_tasks") or [])
    assert tid in (row.get("delegated_tasks") or [])
