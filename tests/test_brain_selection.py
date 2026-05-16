# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.brain.brain_selection import select_brain_for_task
from app.core.config import get_settings


def test_select_brain_forced_deterministic_in_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_PYTEST", "1")
    get_settings.cache_clear()
    try:
        sel = select_brain_for_task("repair_plan", evidence_text="build failed")
        assert sel["selected_provider"] == "deterministic"
    finally:
        get_settings.cache_clear()


def test_select_brain_local_only_prefers_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEXA_PYTEST", raising=False)
    monkeypatch.setenv("USE_REAL_LLM", "true")
    get_settings.cache_clear()
    try:
        s = get_settings()
        monkeypatch.setattr(s, "aethos_privacy_mode", "local_only", raising=False)
        monkeypatch.setattr(s, "nexa_ollama_enabled", True, raising=False)
        sel = select_brain_for_task("repair_plan", settings=s, force_deterministic=False)
        assert sel["selected_provider"] in ("ollama", "deterministic")
    finally:
        get_settings.cache_clear()
