from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services import browser_preview as bp
from app.services import agent_orchestrator
from app.services.web_research_intent import extract_url_for_browser_preview


def _settings(**kwargs) -> SimpleNamespace:
    base: dict = {
        "nexa_browser_preview_enabled": False,
        "nexa_browser_preview_timeout_ms": 35_000,
        "nexa_web_user_agent": "NexaTest/1.0",
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_extract_url_for_browser_preview() -> None:
    u = extract_url_for_browser_preview(" Browser preview  https://example.com/path ")
    assert u == "https://example.com/path"
    assert extract_url_for_browser_preview("check https://a.com") is None


@patch("app.services.browser_preview.get_settings")
def test_disabled_by_default(mock_gs: MagicMock) -> None:
    mock_gs.return_value = _settings(nexa_browser_preview_enabled=False)
    r = bp.preview_public_page("https://example.com", "owner")
    assert r.ok is False
    assert r.error == "disabled"
    assert "NEXA_BROWSER_PREVIEW_ENABLED" in (r.user_message or "")


def test_guest_blocked() -> None:
    with patch("app.services.browser_preview.get_settings", return_value=_settings(nexa_browser_preview_enabled=True)):
        r = bp.preview_public_page("https://example.com", "guest")
    assert r.ok is False
    assert r.error == "owner-only"


def test_private_url_blocked() -> None:
    with patch("app.services.browser_preview.get_settings", return_value=_settings(nexa_browser_preview_enabled=True)):
        r = bp.preview_public_page("http://127.0.0.1:8080/", "owner")
    assert r.ok is False
    joined = f"{r.error} {r.user_message}".lower()
    assert "127" in joined or "internal" in joined or "not" in joined


@patch("app.services.browser_preview._try_import_sync_playwright", return_value=None)
def test_playwright_missing_message(_mock_pw: MagicMock) -> None:
    with patch("app.services.browser_preview.get_settings", return_value=_settings(nexa_browser_preview_enabled=True)):
        r = bp.preview_public_page("https://example.com", "owner")
    assert r.ok is False
    assert "playwright" in (r.user_message or "").lower()
    assert "pip install" in (r.user_message or "").lower()


@patch("app.services.browser_preview._try_import_sync_playwright")
@patch("app.services.browser_preview.get_settings")
def test_happy_path_screenshot(
    mock_gs: MagicMock, mock_import_spw: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_gs.return_value = _settings(nexa_browser_preview_enabled=True)
    monkeypatch.setattr(bp, "PREVIEW_DIR", tmp_path)

    page = MagicMock()
    page.url = "https://example.com/"
    page.title.return_value = "Ex"
    page.content.return_value = (
        "<html><body><p>Visible hello there from browser</p></body></html>"
    )
    page.screenshot.side_effect = lambda path, **k: Path(path).write_bytes(b"fakepng")

    browser = MagicMock()
    browser.new_context.return_value.new_page.return_value = page

    playwright_root = MagicMock()
    playwright_root.chromium.launch.return_value = browser

    ctx_mgr = MagicMock()
    ctx_mgr.__enter__.return_value = playwright_root
    ctx_mgr.__exit__.return_value = None

    def _sync_playwright() -> MagicMock:
        return ctx_mgr

    mock_import_spw.return_value = _sync_playwright
    r = bp.preview_public_page("https://example.com", "owner")
    assert r.ok is True
    assert "hello" in (r.text or "")
    assert r.screenshot_path and Path(r.screenshot_path).is_file()
    page.screenshot.assert_called()


@patch("app.services.browser_preview.format_preview_for_chat", return_value="BROWSER_BODY")
@patch("app.services.browser_preview.preview_public_page")
@patch("app.services.user_capabilities.get_telegram_role_for_app_user", return_value="owner")
def test_research_routes_browser_preview(
    _m_role: MagicMock, m_prev: MagicMock, _m_fmt: MagicMock
) -> None:
    m_prev.return_value = SimpleNamespace(ok=True, user_message="")
    out = agent_orchestrator.handle_research_agent_request(
        MagicMock(), "tg_1", "browser preview https://example.com", conversation_snapshot={}
    )
    m_prev.assert_called()
    assert "BROWSER_BODY" in out
    assert "Research" in out


def test_format_preview_includes_screenshot_path() -> None:
    r = bp.BrowserPreviewResult(
        True,
        "https://example.com/",
        title="T",
        text="body",
        screenshot_path="/tmp/x.png",
    )
    s = bp.format_preview_for_chat(r)
    assert "T" in s
    assert "body" in s
    assert "screenshot" in s.lower()
