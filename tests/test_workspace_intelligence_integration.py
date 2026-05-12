# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Workspace intelligence — optional merge into memory context."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.memory.context_injection import build_memory_context_for_turn


@pytest.fixture
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.usefixtures("_clear_settings_cache")
def test_workspace_intel_appended_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    ws = tmp_path / "wsintel"
    ws.mkdir()
    (ws / "personality.md").write_text("# Personality\nshort.\n", encoding="utf-8")

    monkeypatch.setenv("NEXA_WORKSPACE_INTELLIGENCE_ENABLED", "true")
    monkeypatch.setenv("NEXA_WORKSPACE_INTEL_ROOT", str(ws))
    get_settings.cache_clear()

    out = build_memory_context_for_turn("u_wi", "Say hi about kubernetes", purpose="chat")
    assert out.get("workspace_intel", {}).get("used") is True
    assert "[Workspace intelligence]" in (out.get("memory_context") or "")
