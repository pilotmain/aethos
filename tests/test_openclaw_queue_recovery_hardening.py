# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state


def test_duplicate_queue_entries_reported_then_deduped(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    tid = task_registry.put_task(
        st,
        {"type": "workflow", "user_id": "u1", "state": "queued"},
    )
    st["execution_queue"] = [tid, tid, tid]
    inv1 = validate_runtime_state(st)
    joined = " ".join(inv1.get("issues") or [])
    assert "queue_duplicate_entries" in joined
    removed = task_queue.dedupe_queue_entries(st)
    assert removed >= 2
    inv2 = validate_runtime_state(st)
    joined2 = " ".join(inv2.get("issues") or [])
    assert "queue_duplicate_entries" not in joined2
