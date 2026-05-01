"""Playwright-backed browser automation — gated; public URLs only (Phase 41).

Requires ``pip install playwright`` and ``playwright install chromium`` on the host.
Read paths reuse ``NEXA_BROWSER_PREVIEW_ENABLED``; click/fill require
``NEXA_BROWSER_AUTOMATION_ENABLED=true`` (still no logins / credentials).
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.browser_preview import PREVIEW_DIR, _try_import_sync_playwright
from app.services.web_access import extract_visible_text, validate_public_url_strict


def _timeout_ms() -> int:
    return int(max(5_000, get_settings().nexa_browser_preview_timeout_ms or 35_000))


def _preview_gate() -> tuple[bool, str | None]:
    if not get_settings().nexa_browser_preview_enabled:
        return False, "browser_preview_disabled"
    return True, None


def _automation_gate() -> tuple[bool, str | None]:
    ok, err = _preview_gate()
    if not ok:
        return False, err
    if not get_settings().nexa_browser_automation_enabled:
        return False, "browser_automation_disabled"
    return True, None


def open_page(url: str) -> dict[str, Any]:
    """Navigate to ``url`` and return title + final URL."""
    uerr = validate_public_url_strict(url)
    if uerr:
        return {"ok": False, "error": uerr, "url": url}
    ok, reason = _preview_gate()
    if not ok:
        return {"ok": False, "error": reason, "url": url}
    spw = _try_import_sync_playwright()
    if spw is None:
        return {"ok": False, "error": "playwright_missing", "url": url}
    to_ms = _timeout_ms()
    u = (url or "").strip()
    try:
        with spw() as p:
            browser = p.chromium.launch(headless=True)
            try:
                ctx = browser.new_context(user_agent=get_settings().nexa_web_user_agent)
                page = ctx.new_page()
                page.set_default_timeout(to_ms)
                page.goto(u, wait_until="domcontentloaded", timeout=to_ms)
                page.wait_for_timeout(800)
                return {
                    "ok": True,
                    "url": u,
                    "final_url": page.url,
                    "title": (page.title() or "")[:2000],
                }
            finally:
                browser.close()
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:2000], "url": u}


def extract_content(url: str, *, max_chars: int = 12_000) -> dict[str, Any]:
    """Load page and return visible text."""
    uerr = validate_public_url_strict(url)
    if uerr:
        return {"ok": False, "error": uerr}
    ok, reason = _preview_gate()
    if not ok:
        return {"ok": False, "error": reason}
    spw = _try_import_sync_playwright()
    if spw is None:
        return {"ok": False, "error": "playwright_missing"}
    to_ms = _timeout_ms()
    u = (url or "").strip()
    try:
        with spw() as p:
            browser = p.chromium.launch(headless=True)
            try:
                ctx = browser.new_context(user_agent=get_settings().nexa_web_user_agent)
                page = ctx.new_page()
                page.set_default_timeout(to_ms)
                page.goto(u, wait_until="domcontentloaded", timeout=to_ms)
                page.wait_for_timeout(800)
                html = page.content() or ""
                text = extract_visible_text(html, max_chars=max_chars) or ""
                return {"ok": True, "text": text, "final_url": page.url}
            finally:
                browser.close()
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:2000]}


def screenshot_page(url: str, *, out_dir: Path | None = None) -> dict[str, Any]:
    """Save PNG screenshot; returns path when ``ok``."""
    uerr = validate_public_url_strict(url)
    if uerr:
        return {"ok": False, "error": uerr}
    ok, reason = _preview_gate()
    if not ok:
        return {"ok": False, "error": reason}
    spw = _try_import_sync_playwright()
    if spw is None:
        return {"ok": False, "error": "playwright_missing"}
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    base = out_dir or PREVIEW_DIR
    base.mkdir(parents=True, exist_ok=True)
    shot = base / f"{uuid.uuid4().hex[:12]}.png"
    to_ms = _timeout_ms()
    u = (url or "").strip()
    try:
        with spw() as p:
            browser = p.chromium.launch(headless=True)
            try:
                ctx = browser.new_context(user_agent=get_settings().nexa_web_user_agent)
                page = ctx.new_page()
                page.set_default_timeout(to_ms)
                page.goto(u, wait_until="domcontentloaded", timeout=to_ms)
                page.wait_for_timeout(800)
                page.screenshot(path=str(shot), full_page=False)
                return {"ok": True, "screenshot_path": str(shot), "final_url": page.url}
            finally:
                browser.close()
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:2000]}


def click_selector(url: str, selector: str) -> dict[str, Any]:
    """Click first matching selector after navigation (automation gate)."""
    uerr = validate_public_url_strict(url)
    if uerr:
        return {"ok": False, "error": uerr}
    ok, reason = _automation_gate()
    if not ok:
        return {"ok": False, "error": reason}
    sel = (selector or "").strip()
    if not sel or len(sel) > 500:
        return {"ok": False, "error": "invalid_selector"}
    spw = _try_import_sync_playwright()
    if spw is None:
        return {"ok": False, "error": "playwright_missing"}
    to_ms = _timeout_ms()
    u = (url or "").strip()
    try:
        with spw() as p:
            browser = p.chromium.launch(headless=True)
            try:
                ctx = browser.new_context(user_agent=get_settings().nexa_web_user_agent)
                page = ctx.new_page()
                page.set_default_timeout(to_ms)
                page.goto(u, wait_until="domcontentloaded", timeout=to_ms)
                page.wait_for_timeout(400)
                page.click(sel, timeout=min(to_ms, 30_000))
                return {"ok": True, "final_url": page.url, "clicked": sel}
            finally:
                browser.close()
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:2000]}


def fill_form_field(url: str, selector: str, text: str) -> dict[str, Any]:
    """Fill input/textarea (automation gate)."""
    uerr = validate_public_url_strict(url)
    if uerr:
        return {"ok": False, "error": uerr}
    ok, reason = _automation_gate()
    if not ok:
        return {"ok": False, "error": reason}
    sel = (selector or "").strip()
    if not sel or len(sel) > 500:
        return {"ok": False, "error": "invalid_selector"}
    fill = (text or "")[:50_000]
    spw = _try_import_sync_playwright()
    if spw is None:
        return {"ok": False, "error": "playwright_missing"}
    to_ms = _timeout_ms()
    u = (url or "").strip()
    try:
        with spw() as p:
            browser = p.chromium.launch(headless=True)
            try:
                ctx = browser.new_context(user_agent=get_settings().nexa_web_user_agent)
                page = ctx.new_page()
                page.set_default_timeout(to_ms)
                page.goto(u, wait_until="domcontentloaded", timeout=to_ms)
                page.wait_for_timeout(400)
                page.fill(sel, fill)
                return {"ok": True, "final_url": page.url, "filled": sel}
            finally:
                browser.close()
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:2000]}


def list_visible_links(url: str, *, max_links: int = 40) -> dict[str, Any]:
    """Return up to ``max_links`` absolute hrefs from anchor elements (read-only)."""
    uerr = validate_public_url_strict(url)
    if uerr:
        return {"ok": False, "error": uerr}
    ok, reason = _preview_gate()
    if not ok:
        return {"ok": False, "error": reason}
    spw = _try_import_sync_playwright()
    if spw is None:
        return {"ok": False, "error": "playwright_missing"}
    to_ms = _timeout_ms()
    u = (url or "").strip()
    hrefs: list[str] = []
    try:
        with spw() as p:
            browser = p.chromium.launch(headless=True)
            try:
                ctx = browser.new_context(user_agent=get_settings().nexa_web_user_agent)
                page = ctx.new_page()
                page.set_default_timeout(to_ms)
                page.goto(u, wait_until="domcontentloaded", timeout=to_ms)
                page.wait_for_timeout(600)
                for el in page.query_selector_all("a[href]"):
                    if len(hrefs) >= max_links:
                        break
                    h = el.get_attribute("href")
                    if h:
                        hrefs.append(h)
                return {"ok": True, "links": hrefs, "final_url": page.url}
            finally:
                browser.close()
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:2000]}


__all__ = [
    "click_selector",
    "extract_content",
    "fill_form_field",
    "list_visible_links",
    "open_page",
    "screenshot_page",
]
