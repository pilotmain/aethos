# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import time

from app.orchestration import task_queue
from app.orchestration import task_registry
from app.orchestration import task_scheduler
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_scheduler_tick_advances_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    monkeypatch.setenv("AETHOS_ORCHESTRATION_ENABLE_IN_PYTEST", "1")
    monkeypatch.setenv("AETHOS_ORCHESTRATION_TEST_FAST", "1")
    st = load_runtime_state()
    tid = task_registry.put_task(st, {"type": "noop", "state": "queued"})
    task_queue.enqueue_task_id(st, "execution_queue", tid)
    save_runtime_state(st)
    task_scheduler.stop_scheduler_background()
    task_scheduler.start_scheduler_background()
    for _ in range(200):
        st = load_runtime_state()
        t = task_registry.get_task(st, tid)
        if t and t.get("state") == "completed":
            break
        time.sleep(0.02)
    task_scheduler.stop_scheduler_background()
    st = load_runtime_state()
    assert task_registry.get_task(st, tid)["state"] == "completed"
    sch = (st.get("orchestration") or {}).get("scheduler") or {}
    assert int(sch.get("ticks") or 0) >= 1
