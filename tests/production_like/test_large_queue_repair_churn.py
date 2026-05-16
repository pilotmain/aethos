# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import os

import pytest

from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.corruption.runtime_repair import repair_runtime_queues_and_metrics
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


@pytest.mark.production_like
def test_large_queue_repair_churn(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    n = 90 if os.environ.get("AETHOS_CHURN_LARGE") == "1" else 40
    st = load_runtime_state()
    for i in range(n):
        tid = task_registry.put_task(st, {"id": f"qrc_{i}", "type": "noop", "user_id": "u", "state": "queued"})
        task_queue.enqueue_task_id(st, "execution_queue", str(tid))
        repair_runtime_queues_and_metrics(st)
        if i % 13 == 0:
            repair_runtime_queues_and_metrics(st)
    save_runtime_state(st)
    assert validate_runtime_state(load_runtime_state()).get("ok") is True
