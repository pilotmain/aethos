# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.core.config import get_settings
from app.orchestration import task_queue
from app.runtime.runtime_state import load_runtime_state


def test_enqueue_emits_queue_pressure_near_cap(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    monkeypatch.setenv("AETHOS_QUEUE_LIMIT", "20")
    get_settings.cache_clear()
    try:
        st = load_runtime_state()
        qn = "execution_queue"
        for i in range(19):
            task_queue.enqueue_task_id(st, qn, f"tid_{i}")
        assert int((st.get("runtime_metrics") or {}).get("queue_pressure_events_total") or 0) == 0
        task_queue.enqueue_task_id(st, qn, "tid_pressure")
        assert int((st.get("runtime_metrics") or {}).get("queue_pressure_events_total") or 0) >= 1
    finally:
        get_settings.cache_clear()
