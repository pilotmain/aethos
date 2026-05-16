# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Planning record count stays bounded when retention runs (artifact-like JSON growth)."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.runtime import retention
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state


@pytest.mark.production_like
def test_planning_records_respect_retention_cap(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    monkeypatch.setenv("AETHOS_PLANNING_RECORD_LIMIT", "8")
    get_settings.cache_clear()
    try:
        st = load_runtime_state()
        pr = st.setdefault("planning_records", {})
        for i in range(20):
            pr[f"p{i}"] = {
                "planning_id": f"p{i}",
                "status": "archived",
                "updated_at": f"2026-01-{i % 28 + 1:02d}T00:00:00Z",
                "task_id": "",
                "plan_id": "",
            }
        pr["p_active"] = {
            "planning_id": "p_active",
            "status": "active",
            "updated_at": "2099-01-01T00:00:00Z",
            "task_id": "",
            "plan_id": "",
        }
        retention.trim_planning_records(st)
        assert len(pr) <= 8
        assert "p_active" in pr
        assert validate_runtime_state(st).get("ok") is True
    finally:
        get_settings.cache_clear()
