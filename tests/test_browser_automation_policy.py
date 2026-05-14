# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.services.browser_automation import (
    assert_browser_url_allowed,
    host_browser_screenshot_directory,
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


def test_open_system_browser_adds_https_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        recorded.append(list(cmd))

    monkeypatch.setattr("app.services.browser_automation.subprocess.run", fake_run)
    monkeypatch.setenv("NEXA_BROWSER_ALLOWED_DOMAINS", "*")
    get_settings.cache_clear()
    try:
        with patch("app.services.browser_automation.sys.platform", "darwin"):
            r = open_system_browser("pilotmain.com/foo")
        assert r.get("success") is True
        assert recorded == [["open", "https://pilotmain.com/foo"]]
    finally:
        monkeypatch.delenv("NEXA_BROWSER_ALLOWED_DOMAINS", raising=False)
        get_settings.cache_clear()


def test_take_system_screenshot_darwin_screencapture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("NEXA_BROWSER_SCREENSHOT_DIR", str(tmp_path))
    get_settings.cache_clear()
    recorded: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        recorded.append(list(cmd))
        Path(cmd[-1]).write_bytes(b"\x89PNG\r\n\x1a\n")

    monkeypatch.setattr("app.services.browser_automation.subprocess.run", fake_run)
    try:
        with patch("app.services.browser_automation.sys.platform", "darwin"):
            from app.services.browser_automation import take_system_screenshot

            r = take_system_screenshot(name="t1")
        assert r.get("success") is True
        assert r.get("method") == "system_screenshot"
        assert recorded and recorded[0][:2] == ["screencapture", "-x"]
        assert str(recorded[0][-1]).endswith("t1.png")
    finally:
        monkeypatch.delenv("NEXA_BROWSER_SCREENSHOT_DIR", raising=False)
        get_settings.cache_clear()


def test_run_browser_screenshot_uses_system_capture(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str | None] = []

    def fake_shot(*, name: str | None = None) -> dict:
        calls.append(name)
        return {"success": True, "path": "/tmp/nexa_test_shot.png"}

    monkeypatch.setattr("app.services.browser_automation.take_system_screenshot", fake_shot)
    from app.services.browser_automation import run_browser_host_action_sync

    out = run_browser_host_action_sync("browser_screenshot", {"name": "demo"})
    assert calls == ["demo"]
    assert "Screenshot saved" in out
    assert "/tmp/nexa_test_shot.png" in out


def test_host_browser_screenshot_directory_respects_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    d = tmp_path / "shotdir"
    monkeypatch.setenv("NEXA_BROWSER_SCREENSHOT_DIR", str(d))
    get_settings.cache_clear()
    try:
        out = host_browser_screenshot_directory()
        assert out.resolve() == d.resolve()
        assert out.is_dir()
    finally:
        monkeypatch.delenv("NEXA_BROWSER_SCREENSHOT_DIR", raising=False)
        get_settings.cache_clear()


def test_shutdown_sync_browser_host_session_idempotent() -> None:
    shutdown_sync_browser_host_session()
    shutdown_sync_browser_host_session()
