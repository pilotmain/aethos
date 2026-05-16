# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.core.config import get_settings
from app.runtime.integrity.runtime_cleanup import cleanup_runtime_state
from app.runtime import retention
from app.runtime.runtime_state import load_runtime_state


def test_event_buffer_respects_runtime_buffer_limit_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    monkeypatch.setenv("AETHOS_RUNTIME_EVENT_BUFFER_LIMIT", "6")
    get_settings.cache_clear()
    try:
        st = load_runtime_state()
        st["runtime_event_buffer"] = [{"event_id": str(i), "event": "x", "timestamp": "t"} for i in range(20)]
        out = cleanup_runtime_state(st)
        assert int(out.get("events_trimmed") or 0) >= 14
        buf = st.get("runtime_event_buffer") or []
        assert isinstance(buf, list)
        assert len(buf) < 20
    finally:
        get_settings.cache_clear()


def test_retention_trims_planning_outcomes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    monkeypatch.setenv("AETHOS_PLANNING_OUTCOME_LIMIT", "5")
    get_settings.cache_clear()
    try:
        st = load_runtime_state()
        st["planning_outcomes"] = [{"task_id": f"t{i}", "ok": True} for i in range(12)]
        n = retention.trim_planning_outcomes(st)
        assert n >= 1
        assert len(st.get("planning_outcomes") or []) == 5
    finally:
        get_settings.cache_clear()
