# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_task_registry_persist_restore(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    tid = task_registry.put_task(st, {"type": "noop", "state": "queued", "outputs": []})
    assert tid
    assert task_registry.get_task(st, tid)["state"] == "queued"
    save_runtime_state(st)
    st2 = load_runtime_state()
    t2 = task_registry.get_task(st2, tid)
    assert t2 and t2["type"] == "noop"


def test_task_ownership_fields_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    tid = task_registry.put_task(
        st, {"type": "noop", "state": "running", "owner": "agent-1", "agent_id": "agent-1"}
    )
    task_registry.update_task_state(st, tid, "waiting", reason="gate")
    save_runtime_state(st)
    st2 = load_runtime_state()
    t = task_registry.get_task(st2, tid)
    assert t and t["state"] == "waiting" and t.get("owner") == "agent-1"
