# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.runtime import retention
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state


@pytest.mark.production_like
def test_planning_outcomes_trim_under_cap(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    monkeypatch.setenv("AETHOS_PLANNING_OUTCOME_LIMIT", "12")
    get_settings.cache_clear()
    try:
        st = load_runtime_state()
        st["planning_outcomes"] = [{"task_id": f"t{i}", "ok": True} for i in range(40)]
        retention.trim_planning_outcomes(st)
        assert len(st.get("planning_outcomes") or []) <= 12
        assert validate_runtime_state(st).get("ok") is True
    finally:
        get_settings.cache_clear()
