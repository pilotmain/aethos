# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.core.config import get_settings
from app.execution import execution_plan
from app.execution.execution_supervisor import tick_planned_task
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state


def test_fail_once_respects_step_max_retries_zero(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    monkeypatch.setenv("AETHOS_STEP_MAX_RETRIES", "0")
    get_settings.cache_clear()
    try:
        st = load_runtime_state()
        tid = task_registry.put_task(
            st,
            {"type": "exec", "user_id": "u", "state": "running", "execution_plan_id": ""},
        )
        pid = execution_plan.create_plan(
            st,
            tid,
            [{"step_id": "s1", "status": "queued", "fail_once": True, "retryable": True, "max_retries": 5}],
        )
        tr = task_registry.get_task(st, tid) or {}
        tr["execution_plan_id"] = pid
        task_registry.put_task(st, tr)
        out = tick_planned_task(st, tid, now_ts=1_700_000_000.0)
        assert out and str(out.get("terminal")) == "failed"
        m = st.get("runtime_metrics") or {}
        assert int(m.get("adaptive_retry_blocked_total") or 0) >= 1
    finally:
        get_settings.cache_clear()


def test_tool_retry_exhaustion_respects_step_max_retries(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    monkeypatch.setenv("AETHOS_STEP_MAX_RETRIES", "1")
    get_settings.cache_clear()
    try:
        st = load_runtime_state()
        tid = task_registry.put_task(
            st,
            {"type": "exec", "user_id": "u", "state": "running", "execution_plan_id": ""},
        )
        pid = execution_plan.create_plan(
            st,
            tid,
            [
                {
                    "step_id": "s1",
                    "status": "queued",
                    "retryable": True,
                    "max_retries": 99,
                    "tool": {"name": "not_a_real_tool", "input": {}},
                }
            ],
        )
        tr = task_registry.get_task(st, tid) or {}
        tr["execution_plan_id"] = pid
        task_registry.put_task(st, tr)
        r1 = tick_planned_task(st, tid, now_ts=1_700_000_000.0)
        assert r1 and str(r1.get("terminal")) == "retrying"
        r2 = tick_planned_task(st, tid, now_ts=1_700_000_100.0)
        assert r2 and str(r2.get("terminal")) == "failed"
        m = st.get("runtime_metrics") or {}
        assert int(m.get("retry_exhausted_total") or 0) >= 1
    finally:
        get_settings.cache_clear()
