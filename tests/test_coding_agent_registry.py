# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 24 — coding-agent registry."""

from __future__ import annotations

from app.services.dev_runtime.coding_agents.registry import choose_adapter
from app.services.dev_runtime.coding_agents.local_stub import LocalStubCodingAgent


def test_registry_falls_back_to_local_stub(monkeypatch) -> None:
    monkeypatch.setenv("NEXA_AIDER_ENABLED", "false")
    monkeypatch.setenv("NEXA_CURSOR_AGENT_ENABLED", "false")
    monkeypatch.setenv("NEXA_CLAUDE_CODE_ENABLED", "false")
    monkeypatch.setenv("NEXA_CODEX_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    a = choose_adapter(preferred="does_not_exist")
    assert isinstance(a, LocalStubCodingAgent)
    assert a.name == "local_stub"


def test_preferred_local_stub(monkeypatch) -> None:
    monkeypatch.setenv("NEXA_AIDER_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    a = choose_adapter(preferred="local_stub")
    assert a.name == "local_stub"
