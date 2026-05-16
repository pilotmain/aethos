# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.runtime.runtime_agents import release_runtime_agent, spawn_runtime_agent, sweep_expired_agents
from app.runtime.runtime_state import default_runtime_state, save_runtime_state


def test_release_after_assignment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path / "home"))
    get_settings.cache_clear()
    try:
        save_runtime_state(default_runtime_state(workspace_root=tmp_path / "ws"))
        row = spawn_runtime_agent(agent_type="repair", ttl_sec=120)
        aid = str(row["agent_id"])
        from app.runtime.runtime_agents import assign_runtime_agent

        assign_runtime_agent(aid, task_id="t1")
        released = release_runtime_agent(aid)
        assert released is not None
        assert released.get("status") == "idle"
        sweep_expired_agents()
    finally:
        get_settings.cache_clear()
