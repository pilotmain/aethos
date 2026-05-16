# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


@pytest.mark.production_like
def test_queue_pressure_with_retries_under_cap(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    monkeypatch.setenv("AETHOS_QUEUE_LIMIT", "120")
    get_settings.cache_clear()
    try:
        st = load_runtime_state()
        qn = "execution_queue"
        for i in range(100):
            tid = f"prod_q_{i}"
            task_registry.put_task(st, {"id": tid, "type": "noop", "user_id": "u1", "state": "retrying"})
            task_queue.enqueue_task_id(st, qn, tid)
        save_runtime_state(st)
        assert validate_runtime_state(load_runtime_state()).get("ok") is True
    finally:
        get_settings.cache_clear()
