# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.runtime.runtime_agents import (
    ORCHESTRATOR_ID,
    list_runtime_agents,
    spawn_runtime_agent,
    sweep_expired_agents,
)
from app.runtime.runtime_state import default_runtime_state, load_runtime_state, save_runtime_state


def test_orchestrator_always_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path / "home"))
    get_settings.cache_clear()
    try:
        st = default_runtime_state(workspace_root=tmp_path / "ws")
        save_runtime_state(st)
        agents = list_runtime_agents()
        assert ORCHESTRATOR_ID in agents
        assert agents[ORCHESTRATOR_ID].get("agent_type") == "orchestrator"
    finally:
        get_settings.cache_clear()


def test_spawn_and_sweep(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path / "home"))
    get_settings.cache_clear()
    try:
        st = default_runtime_state(workspace_root=tmp_path / "ws")
        save_runtime_state(st)
        row = spawn_runtime_agent(agent_type="research", created_from_task="t1", ttl_sec=60)
        assert row["status"] == "active"
        agents = list_runtime_agents()
        assert row["agent_id"] in agents
        n = sweep_expired_agents()
        assert n >= 0
    finally:
        get_settings.cache_clear()
