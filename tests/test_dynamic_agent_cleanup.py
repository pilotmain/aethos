# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.runtime.runtime_agents import spawn_or_reuse_runtime_agent
from app.runtime.runtime_state import default_runtime_state, save_runtime_state


def test_spawn_or_reuse_same_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path / "home"))
    get_settings.cache_clear()
    try:
        save_runtime_state(default_runtime_state(workspace_root=tmp_path / "ws"))
        a = spawn_or_reuse_runtime_agent(agent_type="repair", created_from_task="fix:x")
        b = spawn_or_reuse_runtime_agent(agent_type="repair", created_from_task="fix:x")
        assert a["agent_id"] == b["agent_id"]
    finally:
        get_settings.cache_clear()
