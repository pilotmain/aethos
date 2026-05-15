# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Playwright-backed browser automation — gated; public URLs only (Phase 41).

Requires ``pip install playwright`` and ``playwright install chromium`` on the host.
Read paths reuse ``NEXA_BROWSER_PREVIEW_ENABLED``; click/fill require
``NEXA_BROWSER_AUTOMATION_ENABLED=true`` (still no logins / credentials).
"""

from __future__ import annotations

import json
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


def _transient_playwright_error(msg: str) -> bool:
    m = (msg or "").lower()
    return any(
        x in m
        for x in (
            "timeout",
            "navigation",
            "net::err",
            "target page",
            "crash",
            "connection",
            "ns_error",
        )
    )


def _navigation_error_hint(msg: str) -> bool:
    return any(x in (msg or "").lower() for x in ("navigation", "404", "500", "net::err", "dns"))


def _goto_with_retry(page: Any, url: str, *, to_ms: int, max_attempts: int = 3) -> None:
    last_exc: Exception | None = None
    for att in range(max_attempts):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=to_ms)
            return
        except Exception as exc:
            last_exc = exc
            if att < max_attempts - 1 and _transient_playwright_error(str(exc)):
                page.wait_for_timeout(min(2500, 350 * (att + 1)))
                continue
    if last_exc:
        raise last_exc
    raise RuntimeError("goto_failed")


def _append_workflow_memory(session_id: str, record: dict[str, Any]) -> None:
    """Append one JSON line per workflow step (Phase 46B — navigation memory)."""
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    sid = (session_id or "default")[:48]
    p = PREVIEW_DIR / f"browser_workflow_{sid}.jsonl"
    line = json.dumps({**record, "session": sid}, ensure_ascii=False, default=str)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_browser_workflow(
    steps: list[dict[str, Any]],
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    Multi-step public-site automation in one browser session (no credential storage).

    Each step: ``{"action": "open"|"click"|"fill"|"extract"|"wait", ...}``.
    """
    ok, reason = _automation_gate()
    if not ok:
        return {"ok": False, "error": reason, "results": []}
    if not any(isinstance(step, dict) for step in steps):
        sid = (session_id or uuid.uuid4().hex[:20])[:48]
        return {
            "ok": True,
            "session_id": sid,
            "results": [{"i": i, "ok": False, "error": "invalid_step"} for i, _ in enumerate(steps)],
        }
    spw = _try_import_sync_playwright()
    if spw is None:
        return {"ok": False, "error": "playwright_missing", "results": []}
    sid = (session_id or uuid.uuid4().hex[:20])[:48]
    to_ms = _timeout_ms()
    results: list[dict[str, Any]] = []
    try:
        with spw() as p:
            browser = p.chromium.launch(headless=True)
            try:
                ctx = browser.new_context(user_agent=get_settings().nexa_web_user_agent)
                page = ctx.new_page()
                page.set_default_timeout(to_ms)
                for i, step in enumerate(steps):
                    if not isinstance(step, dict):
                        results.append({"i": i, "ok": False, "error": "invalid_step"})
                        continue
                    act = str(step.get("action") or "").lower().strip()
                    rec: dict[str, Any] = {"i": i, "action": act}
                    try:
                        if act == "open":
                            u = str(step.get("url") or "").strip()
                            err = validate_public_url_strict(u)
                            if err:
                                rec.update({"ok": False, "error": err})
                            else:
                                _goto_with_retry(page, u, to_ms=to_ms)
                                page.wait_for_timeout(400)
                                rec.update({"ok": True, "final_url": page.url})
                        elif act == "click":
                            u = str(step.get("url") or "").strip()
                            sel = str(step.get("selector") or "").strip()
                            err = validate_public_url_strict(u)
                            if err:
                                rec.update({"ok": False, "error": err})
                            elif not sel:
                                rec.update({"ok": False, "error": "missing_selector"})
                            else:
                                _goto_with_retry(page, u, to_ms=to_ms)
                                page.wait_for_timeout(300)
                                for catt in range(3):
                                    try:
                                        page.click(sel, timeout=min(to_ms, 30_000))
                                        break
                                    except Exception as cexc:
                                        if catt < 2 and _transient_playwright_error(str(cexc)):
                                            page.wait_for_timeout(300 * (catt + 1))
                                            continue
                                        raise
                                rec.update({"ok": True, "final_url": page.url, "clicked": sel})
                        elif act == "fill":
                            u = str(step.get("url") or "").strip()
                            sel = str(step.get("selector") or "").strip()
                            text = str(step.get("text") or "")[:50_000]
                            err = validate_public_url_strict(u)
                            if err:
                                rec.update({"ok": False, "error": err})
                            elif not sel:
                                rec.update({"ok": False, "error": "missing_selector"})
                            else:
                                _goto_with_retry(page, u, to_ms=to_ms)
                                page.wait_for_timeout(300)
                                page.fill(sel, text)
                                rec.update({"ok": True, "final_url": page.url})
                        elif act == "extract":
                            u = str(step.get("url") or "").strip()
                            mx = int(step.get("max_chars") or 12_000)
                            err = validate_public_url_strict(u)
                            if err:
                                rec.update({"ok": False, "error": err})
                            else:
                                _goto_with_retry(page, u, to_ms=to_ms)
                                page.wait_for_timeout(500)
                                html = page.content() or ""
                                txt = extract_visible_text(html, max_chars=mx) or ""
                                if len(txt.strip()) < 20:
                                    try:
                                        alt = (page.inner_text("body") or "")[:mx]
                                        if len(alt) > len(txt):
                                            txt = alt
                                            rec["extract_fallback"] = "inner_text_body"
                                    except Exception:
                                        pass
                                rec.update({"ok": True, "text": txt[:mx], "final_url": page.url})
                        elif act == "wait":
                            ms = int(step.get("ms") or 800)
                            page.wait_for_timeout(min(30_000, max(100, ms)))
                            rec.update({"ok": True, "final_url": page.url})
                        else:
                            rec.update({"ok": False, "error": f"unknown_action:{act}"})
                    except Exception as exc:
                        rec.update(
                            {
                                "ok": False,
                                "error": str(exc)[:2000],
                                "navigation_error": _navigation_error_hint(str(exc)),
                            }
                        )
                    _append_workflow_memory(sid, rec)
                    results.append(rec)
                return {"ok": True, "session_id": sid, "results": results}
            finally:
                browser.close()
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:2000], "results": results}


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
    "run_browser_workflow",
    "screenshot_page",
]
