# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.gateway.operator_intent_router import execute_provider_nl_intent
from app.gateway.provider_intents import parse_provider_operation_intent
from app.runtime.runtime_state import default_runtime_state, save_runtime_state


def test_unknown_project_suggests_link(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "ahome"
    home.mkdir()
    monkeypatch.setenv("AETHOS_HOME_DIR", str(home))
    get_settings.cache_clear()
    try:
        st = default_runtime_state(workspace_root=tmp_path / "ws")
        save_runtime_state(st)
        parsed = parse_provider_operation_intent("restart unknown-project-xyz")
        assert parsed is not None
        out = execute_provider_nl_intent(parsed)
        text = out.get("text") or ""
        assert "projects link" in text.lower() or "candidates" in text.lower()
        assert "enoent" not in text.lower()
    finally:
        get_settings.cache_clear()
