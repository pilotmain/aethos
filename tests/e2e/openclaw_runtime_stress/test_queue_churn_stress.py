# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.core.config import get_settings
from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_many_queue_ops_stay_valid(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    monkeypatch.setenv("AETHOS_QUEUE_LIMIT", "200")
    get_settings.cache_clear()
    try:
        st = load_runtime_state()
        tid = "stress_tid"
        for i in range(150):
            tid_i = f"{tid}_{i}"
            task_registry.put_task(st, {"id": tid_i, "type": "noop", "user_id": "u1", "state": "queued"})
            task_queue.enqueue_task_id(st, "execution_queue", tid_i)
            if i % 10 == 0:
                task_queue.remove_task_id_from_all_queues(st, f"{tid}_{i}")
        save_runtime_state(st)
        assert validate_runtime_state(load_runtime_state()).get("ok") is True
    finally:
        get_settings.cache_clear()
