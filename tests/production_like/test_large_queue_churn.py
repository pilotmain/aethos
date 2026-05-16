# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from tests.parity_freeze_gate import repeated_cycles


@pytest.mark.production_like
def test_large_queue_churn(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    monkeypatch.setenv("AETHOS_QUEUE_LIMIT", "500")
    get_settings.cache_clear()
    try:
        n = repeated_cycles(large=250)
        st = load_runtime_state()
        for i in range(n):
            tid = f"churn_{i}"
            task_registry.put_task(st, {"id": tid, "type": "noop", "user_id": "u", "state": "queued"})
            task_queue.enqueue_task_id(st, "execution_queue", tid)
            if i % 7 == 0:
                task_queue.remove_task_id_from_all_queues(st, tid)
        save_runtime_state(st)
        assert validate_runtime_state(load_runtime_state()).get("ok") is True
    finally:
        get_settings.cache_clear()
