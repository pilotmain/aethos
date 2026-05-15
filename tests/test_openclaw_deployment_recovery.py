# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.orchestration import runtime_dispatcher
from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_deployment_task_survives_dispatch_checkpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    tid = task_registry.put_task(st, {"type": "deploy", "state": "queued", "outputs": ["log:plan"]})
    task_queue.enqueue_task_id(st, "execution_queue", tid)
    runtime_dispatcher.dispatch_once(st)
    save_runtime_state(st)
    st2 = load_runtime_state()
    assert task_registry.get_task(st2, tid)["state"] == "completed"
    cp = (st2.get("orchestration") or {}).get("checkpoints") or {}
    assert cp.get(tid, {}).get("step") == "deployed"
    deps = st2.get("deployments") or []
    assert any(isinstance(d, dict) and d.get("task_id") == tid for d in deps)
