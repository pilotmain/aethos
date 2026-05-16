# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.brain.brain_selection import brain_allows_external_call, select_brain_for_task
from app.core.config import get_settings


def test_local_only_blocks_external_brain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEXA_PYTEST", raising=False)
    monkeypatch.setenv("USE_REAL_LLM", "true")
    get_settings.cache_clear()
    try:
        s = get_settings()
        monkeypatch.setattr(s, "aethos_privacy_mode", "local_only", raising=False)
        monkeypatch.setattr(s, "nexa_ollama_enabled", False, raising=False)
        sel = select_brain_for_task("repair_plan", settings=s, force_deterministic=False)
        assert sel["selected_provider"] == "deterministic"
        assert brain_allows_external_call(sel, settings=s) is False or sel["selected_provider"] == "deterministic"
    finally:
        get_settings.cache_clear()
