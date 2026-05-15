# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.orchestration import runtime_dispatcher
from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_checkpoint_written_on_noop_complete(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    tid = task_registry.put_task(st, {"type": "noop", "state": "queued"})
    task_queue.enqueue_task_id(st, "execution_queue", tid)
    runtime_dispatcher.dispatch_once(st)
    save_runtime_state(st)
    st2 = load_runtime_state()
    cp = (st2.get("orchestration") or {}).get("checkpoints") or {}
    assert tid in cp and cp[tid].get("step") == "done"
