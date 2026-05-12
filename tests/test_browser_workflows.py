# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 46B — multi-step browser workflows (gated)."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.system_access.browser_playwright import run_browser_workflow


def test_run_browser_workflow_disabled_when_automation_off(monkeypatch) -> None:
    monkeypatch.setenv("NEXA_BROWSER_AUTOMATION_ENABLED", "false")
    get_settings.cache_clear()
    try:
        r = run_browser_workflow([{"action": "open", "url": "https://example.com"}])
        assert r.get("ok") is False
        assert r.get("results") == []
        assert r.get("error")
    finally:
        monkeypatch.delenv("NEXA_BROWSER_AUTOMATION_ENABLED", raising=False)
        get_settings.cache_clear()


def test_run_browser_workflow_invalid_step(monkeypatch) -> None:
    pytest.importorskip("playwright.sync_api")
    monkeypatch.setenv("NEXA_BROWSER_PREVIEW_ENABLED", "true")
    monkeypatch.setenv("NEXA_BROWSER_AUTOMATION_ENABLED", "true")
    get_settings.cache_clear()
    try:
        r = run_browser_workflow(["not-a-dict"])
        assert r.get("ok") is True
        assert any(x.get("error") == "invalid_step" for x in (r.get("results") or []))
    finally:
        monkeypatch.delenv("NEXA_BROWSER_PREVIEW_ENABLED", raising=False)
        monkeypatch.delenv("NEXA_BROWSER_AUTOMATION_ENABLED", raising=False)
        get_settings.cache_clear()
