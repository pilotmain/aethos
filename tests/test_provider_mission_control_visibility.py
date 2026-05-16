# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.runtime.runtime_state import default_runtime_state, save_runtime_state
from app.services.operator_context import build_operator_context_panel


def test_operator_context_includes_nl_actions(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "ahome"
    home.mkdir()
    monkeypatch.setenv("AETHOS_HOME_DIR", str(home))
    get_settings.cache_clear()
    try:
        st = default_runtime_state(workspace_root=tmp_path / "ws")
        st["operator_provider_actions"] = [
            {"source": "gateway_nl", "intent": "provider_restart", "project_id": "x", "success": True}
        ]
        save_runtime_state(st)
        panel = build_operator_context_panel()
        assert "recent_nl_provider_actions" in panel
        assert len(panel.get("recent_nl_provider_actions") or []) == 1
        assert panel.get("last_nl_provider_action", {}).get("intent") == "provider_restart"
    finally:
        get_settings.cache_clear()
