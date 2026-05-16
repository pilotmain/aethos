# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import os

import pytest

from app.core.config import get_settings
from app.execution import execution_plan
from app.execution.execution_supervisor import tick_planned_task
from app.orchestration import task_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state


@pytest.mark.production_like
def test_large_retry_churn(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    monkeypatch.setenv("AETHOS_STEP_MAX_RETRIES", "1")
    get_settings.cache_clear()
    try:
        rounds = 12 if os.environ.get("AETHOS_CHURN_LARGE") == "1" else 5
        for _ in range(rounds):
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
            tick_planned_task(st, tid, now_ts=1_701_000_000.0)
            tick_planned_task(st, tid, now_ts=1_701_000_100.0)
        assert validate_runtime_state(load_runtime_state()).get("ok") is True
    finally:
        get_settings.cache_clear()
