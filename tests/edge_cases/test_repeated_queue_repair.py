# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.corruption.runtime_repair import repair_runtime_queues_and_metrics
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state


@pytest.mark.edge_cases
def test_repeated_queue_repair_idempotent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    tid = task_registry.put_task(st, {"id": "edge_q", "type": "noop", "user_id": "u", "state": "queued"})
    task_queue.enqueue_task_id(st, "execution_queue", str(tid))
    for _ in range(40):
        repair_runtime_queues_and_metrics(st)
    inv = validate_runtime_state(st)
    assert inv.get("ok") is True
