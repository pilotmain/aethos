# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.services.browser_automation import (
    assert_browser_url_allowed,
    open_system_browser,
    shutdown_sync_browser_host_session,
)


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


def test_open_system_browser_blocked_by_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_BROWSER_ALLOWED_DOMAINS", "example.com")
    get_settings.cache_clear()
    try:
        r = open_system_browser("https://evil.test/")
        assert r["success"] is False
        assert "not allowed" in (r.get("error") or "").lower()
    finally:
        monkeypatch.delenv("NEXA_BROWSER_ALLOWED_DOMAINS", raising=False)
        get_settings.cache_clear()


def test_open_system_browser_darwin_invokes_open(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        recorded.append(list(cmd))

    monkeypatch.setattr("app.services.browser_automation.subprocess.run", fake_run)
    monkeypatch.setenv("NEXA_BROWSER_ALLOWED_DOMAINS", "*")
    get_settings.cache_clear()
    try:
        with patch("app.services.browser_automation.sys.platform", "darwin"):
            r = open_system_browser("https://pilotmain.com/path")
        assert r.get("success") is True
        assert r.get("method") == "system_browser"
        assert recorded == [["open", "https://pilotmain.com/path"]]
    finally:
        monkeypatch.delenv("NEXA_BROWSER_ALLOWED_DOMAINS", raising=False)
        get_settings.cache_clear()


def test_shutdown_sync_browser_host_session_idempotent() -> None:
    shutdown_sync_browser_host_session()
    shutdown_sync_browser_host_session()
