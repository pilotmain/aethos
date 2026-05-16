# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.worker_operational_memory import build_worker_memory, update_worker_memory


def test_worker_memory_bounded() -> None:
    wid = "agent_test_mem"
    update_worker_memory(worker_id=wid, task_id="t1", failure="err")
    mem = build_worker_memory(wid)
    assert mem.get("worker_id") == wid
    assert "t1" in (mem.get("recent_tasks") or [])
