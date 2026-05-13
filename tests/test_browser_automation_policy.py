# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.browser_automation import assert_browser_url_allowed


def test_browser_allowed_domains_star(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_BROWSER_ALLOWED_DOMAINS", "*")
    get_settings.cache_clear()
    try:
        assert_browser_url_allowed("https://any.example/foo")
    finally:
        monkeypatch.delenv("NEXA_BROWSER_ALLOWED_DOMAINS", raising=False)
        get_settings.cache_clear()


def test_browser_allowed_domains_restricts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_BROWSER_ALLOWED_DOMAINS", "example.com,*.safe.test")
    get_settings.cache_clear()
    try:
        assert_browser_url_allowed("https://example.com/")
        assert_browser_url_allowed("https://sub.safe.test/x")
        with pytest.raises(ValueError, match="not allowed"):
            assert_browser_url_allowed("https://evil.com/")
    finally:
        monkeypatch.delenv("NEXA_BROWSER_ALLOWED_DOMAINS", raising=False)
        get_settings.cache_clear()
