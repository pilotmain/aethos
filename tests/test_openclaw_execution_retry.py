# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.execution_plan import create_plan, get_plan
from app.execution.execution_retry import compute_backoff_seconds, schedule_step_retry
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_retry_backoff_and_schedule_persist(tmp_path, monkeypatch) -> None:
    assert compute_backoff_seconds(1) == 1.0
    assert compute_backoff_seconds(3) == 4.0
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    pid = create_plan(st, "t1", [{"step_id": "s1"}])
    p = get_plan(st, pid)
    assert p
    step = p["steps"][0]
    schedule_step_retry(p, step, "boom", now_ts=1000.0)
    assert step["status"] == "retrying"
    assert step["retry_count"] == 1
    assert float(step["next_retry_at"]) > 1000.0
    save_runtime_state(st)
    st2 = load_runtime_state()
    s2 = get_plan(st2, pid)["steps"][0]
    assert s2["failure_reason"] == "boom"
