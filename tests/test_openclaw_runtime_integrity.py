# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state
from app.runtime.integrity.runtime_integrity import validate_runtime_state


def test_integrity_flags_orphan_queue_ref(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    task_registry.put_task(st, {"type": "noop", "user_id": "u", "state": "queued"})
    task_queue.enqueue_task_id(st, "execution_queue", "missing-task-id")
    inv = validate_runtime_state(st)
    assert inv["ok"] is False
    assert any("queue_orphan_ref" in str(x) for x in inv.get("issues") or [])


def test_integrity_ok_on_empty_runtime(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    inv = validate_runtime_state(st)
    assert inv["ok"] is True
    save_runtime_state(st)
