# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 42 — Playwright helpers respect gates (no Chromium required for CI)."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.system_access.browser_playwright import list_visible_links, open_page


def test_open_page_disabled_without_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_BROWSER_PREVIEW_ENABLED", "false")
    get_settings.cache_clear()
    try:
        r = open_page("https://example.com/")
        assert r.get("ok") is False
        assert r.get("error") == "browser_preview_disabled"
    finally:
        monkeypatch.delenv("NEXA_BROWSER_PREVIEW_ENABLED", raising=False)
        get_settings.cache_clear()


def test_list_visible_links_requires_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_BROWSER_PREVIEW_ENABLED", "false")
    get_settings.cache_clear()
    try:
        r = list_visible_links("https://example.com/")
        assert r.get("ok") is False
    finally:
        monkeypatch.delenv("NEXA_BROWSER_PREVIEW_ENABLED", raising=False)
        get_settings.cache_clear()
