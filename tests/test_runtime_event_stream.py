# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.services.mission_control.mc_runtime_events import emit_mc_runtime_event, recent_mc_runtime_events
from app.runtime.runtime_state import default_runtime_state, save_runtime_state


def test_emit_mc_event_persisted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path / "home"))
    get_settings.cache_clear()
    try:
        st = default_runtime_state(workspace_root=tmp_path / "ws")
        save_runtime_state(st)
        emit_mc_runtime_event("repair_started", project_id="acme")
        events = recent_mc_runtime_events(limit=10)
        assert any(
            e.get("event_type") == "repair_started"
            or e.get("event") == "repair_started"
            or e.get("mc_event_type") == "repair_started"
            for e in events
        )
    finally:
        get_settings.cache_clear()
