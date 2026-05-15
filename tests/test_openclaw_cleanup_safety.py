# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.orchestration import task_registry
from app.runtime.integrity.runtime_cleanup import cleanup_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_cleanup_preserves_active_task_and_prunes_orphan_queue_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    tid = task_registry.put_task(
        st,
        {"type": "workflow", "user_id": "u1", "state": "running"},
    )
    st.setdefault("execution_queue", []).extend([tid, "ghost_task_id"])
    cleanup_runtime_state(st)
    save_runtime_state(st)
    st2 = load_runtime_state()
    assert task_registry.get_task(st2, tid) is not None
    assert "ghost_task_id" not in (st2.get("execution_queue") or [])
