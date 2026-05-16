# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.execution import execution_checkpoint
from app.execution import execution_plan
from app.orchestration import task_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state


@pytest.mark.production_like
def test_checkpoint_keys_per_plan_under_cap(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    cap = 35
    monkeypatch.setenv("AETHOS_PLAN_CHECKPOINT_LIMIT", str(cap))
    get_settings.cache_clear()
    try:
        st = load_runtime_state()
        tid = task_registry.put_task(st, {"id": "cp_t", "type": "noop", "user_id": "u", "state": "queued"})
        pid = execution_plan.create_plan(st, tid, [{"step_id": "only", "status": "queued", "type": "noop"}])
        for i in range(min(cap - 2, 20)):
            execution_checkpoint.save_checkpoint(st, pid, f"step_{i}", task_id=tid, outputs=[{"i": i}])
        cps = execution_plan.execution_root(st).get("checkpoints") or {}
        plan_cp = cps.get(pid) or {}
        assert len(plan_cp) < cap
        assert validate_runtime_state(st).get("ok") is True
    finally:
        get_settings.cache_clear()
