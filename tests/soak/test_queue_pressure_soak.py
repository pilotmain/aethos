# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import os

import pytest

from app.core.config import get_settings
from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


@pytest.mark.soak
def test_queue_depth_stays_under_cap(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    lim = 80 if os.environ.get("AETHOS_SOAK_LONG") == "1" else 40
    monkeypatch.setenv("AETHOS_QUEUE_LIMIT", str(lim))
    get_settings.cache_clear()
    try:
        st = load_runtime_state()
        qn = "execution_queue"
        for i in range(lim - 5):
            tid = f"soak_tid_{i}"
            task_registry.put_task(st, {"id": tid, "type": "noop", "user_id": "u1", "state": "queued"})
            task_queue.enqueue_task_id(st, qn, tid)
        task_queue.remove_task_id_from_all_queues(st, "soak_tid_0")
        save_runtime_state(st)
        inv = validate_runtime_state(load_runtime_state())
        assert inv.get("ok") is True
        assert task_queue.queue_len(load_runtime_state(), qn) < lim
    finally:
        get_settings.cache_clear()
