# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Host-executor browser helpers: URL allowlist + sync Playwright (reused session)."""

from __future__ import annotations

import logging
import re
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Host executor calls ``run_browser_host_action_sync`` from sync code, often via ``asyncio.run()``
# in a worker thread. A module-level **async** Playwright tied to a closed event loop breaks the
# next ``open`` ("handler is closed"). Keep a dedicated **sync** Playwright session for this path.
_sync_lock = threading.Lock()
_sync_pw: Any = None
_sync_browser: Any = None
_sync_context: Any = None
_sync_page: Any = None


def _reset_sync_browser_session_locked() -> None:
    global _sync_pw, _sync_browser, _sync_context, _sync_page
    if _sync_page is not None:
        try:
            _sync_page.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug("sync browser page close: %s", exc)
        _sync_page = None
    if _sync_context is not None:
        try:
            _sync_context.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug("sync browser context close: %s", exc)
        _sync_context = None
    if _sync_browser is not None:
        try:
            _sync_browser.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug("sync browser close: %s", exc)
        _sync_browser = None
    if _sync_pw is not None:
        try:
            _sync_pw.stop()
        except Exception as exc:  # noqa: BLE001
            logger.debug("sync playwright stop: %s", exc)
        _sync_pw = None


def _get_sync_host_browser_page():
    """Return a shared sync Playwright page (lazy start, reused across consecutive host actions)."""
    from playwright.sync_api import sync_playwright

    global _sync_pw, _sync_browser, _sync_context, _sync_page

    with _sync_lock:
        s = get_settings()
        sec = getattr(s, "nexa_browser_timeout_seconds", None)
        if sec is not None:
            try:
                timeout_ms = max(int(sec), 1) * 1000
            except (TypeError, ValueError):
                timeout_ms = int(getattr(s, "nexa_browser_timeout", 30000) or 30000)
        else:
            timeout_ms = int(getattr(s, "nexa_browser_timeout", 30000) or 30000)

        if _sync_page is not None:
            try:
                if not _sync_page.is_closed():
                    _sync_page.set_default_timeout(timeout_ms)
                    return _sync_page
            except Exception as exc:  # noqa: BLE001
                logger.warning("sync browser session stale, restarting: %s", exc)
            _reset_sync_browser_session_locked()

        _sync_pw = sync_playwright().start()
        headless = bool(getattr(s, "nexa_browser_headless", True))
        _sync_browser = _sync_pw.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
            ],
        )
        _sync_context = _sync_browser.new_context(
            user_agent=getattr(s, "nexa_web_user_agent", None) or "AethOSBrowser/1.0",
        )
        _sync_page = _sync_context.new_page()
        _sync_page.set_default_timeout(timeout_ms)
        logger.info("sync host browser session started headless=%s", headless)
        return _sync_page


def shutdown_sync_browser_host_session() -> None:
    """Close the sync Playwright session used by :func:`run_browser_host_action_sync` (API shutdown)."""
    with _sync_lock:
        _reset_sync_browser_session_locked()


def assert_browser_url_allowed(url: str) -> None:
    """
    Enforce :envvar:`NEXA_BROWSER_ALLOWED_DOMAINS` (comma-separated hostnames, ``*.suffix``, or ``*``).
    """
    s = get_settings()
    raw = (getattr(s, "nexa_browser_allowed_domains", None) or "*").strip()
    if raw in ("*", "", "*/*"):
        return
    try:
        parsed = urlparse((url or "").strip())
        host = (parsed.hostname or "").lower().strip(".")
    except ValueError as exc:
        raise ValueError("invalid URL for browser navigation") from exc
    if not host:
        raise ValueError("browser navigation requires a URL with a hostname")
    allowed = False
    for part in raw.split(","):
        rule = part.strip().lower().strip(".").strip()
        if not rule:
            continue
        if rule.startswith("*."):
            suf = rule[2:]
            if host == suf or host.endswith("." + suf):
                allowed = True
                break
        elif host == rule or host.endswith("." + rule):
            allowed = True
            break
    if not allowed:
        raise ValueError(f"URL host {host!r} is not allowed by NEXA_BROWSER_ALLOWED_DOMAINS")


def _sanitize_selector(raw: str) -> str:
    s = (raw or "").strip().strip('`"\'')
    if not s or len(s) > 2000:
        raise ValueError("selector empty or too long (max 2000)")
    if "\n" in s or "\r" in s or "\x00" in s:
        raise ValueError("selector contains disallowed characters")
    return s


def default_browser_timeout_ms() -> int:
    """Default Playwright timeout (ms) from Settings."""
    s = get_settings()
    sec = getattr(s, "nexa_browser_timeout_seconds", None)
    if sec is not None:
        try:
            return max(int(sec), 1) * 1000
        except (TypeError, ValueError):
            pass
    return int(getattr(s, "nexa_browser_timeout", 30000) or 30000)


def ensure_browser_ready() -> bool:
    """
    Best-effort check that Playwright is available; optionally install Chromium for browser automation.

    Returns True if the ``playwright`` package imports; install step is non-fatal (check=False).
    """
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    try:
        subprocess.run(
            ["playwright", "install", "chromium"],
            check=False,
            capture_output=True,
            timeout=600,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
    return True


def run_browser_host_action_sync(action: str, payload: dict[str, Any]) -> str:
    """
    Run a allowlisted browser host_action from synchronous :func:`~app.services.host_executor.execute_payload`.

    ``action`` is one of: ``browser_open``, ``browser_click``, ``browser_fill``, ``browser_screenshot``.

    Uses a process-wide **sync** Playwright browser/page so consecutive ``open`` commands reuse the
    same tab instead of hitting a stale async driver after per-call ``asyncio.run()`` teardown.
    """
    act = (action or "").strip().lower()
    timeout_ms = default_browser_timeout_ms()
    op_timeout = min(max(timeout_ms, 1000), 120_000)
    page = _get_sync_host_browser_page()
    page.set_default_timeout(op_timeout)

    if act == "browser_open":
        url = str(payload.get("url") or "").strip()
        if not url:
            raise ValueError("browser_open requires url")
        assert_browser_url_allowed(url)
        page.goto(url, wait_until="domcontentloaded", timeout=op_timeout)
        title = page.title()
        return f"Navigated to {url}\nTitle: {title}"
    if act == "browser_click":
        sel = _sanitize_selector(str(payload.get("selector") or ""))
        page.click(sel, timeout=op_timeout)
        return f"Clicked: {sel}"
    if act == "browser_fill":
        sel = _sanitize_selector(str(payload.get("selector") or ""))
        text = str(payload.get("text") or "")
        if not text:
            raise ValueError("browser_fill requires text")
        if len(text) > 50_000:
            raise ValueError("text too long (max 50000)")
        page.fill(sel, text, timeout=op_timeout)
        return f"Filled {sel}"
    if act == "browser_screenshot":
        settings = get_settings()
        screenshot_dir = Path(settings.nexa_browser_screenshot_dir or "")
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        name = str(payload.get("name") or "").strip() or None
        stem = name or f"screenshot_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.png"
        if not str(stem).lower().endswith(".png"):
            stem = f"{stem}.png"
        path = screenshot_dir / stem
        page.screenshot(path=str(path), full_page=True)
        return f"Screenshot saved: {path}"
    raise ValueError(f"unknown browser host action {act!r}")


_RE_BROWSER_OPEN = re.compile(r"(?is)^(?:open|goto)\s+(https?://\S+)$")
_RE_BROWSER_NAV = re.compile(r"(?is)^navigate\s+to\s+(https?://\S+)$")
_RE_BROWSER_CLICK = re.compile(r"(?is)^click\s+(.+)$")
_RE_BROWSER_TYPE_INTO = re.compile(r"(?is)^type\s+(.+?)\s+into\s+(.+)$")
_RE_BROWSER_SCREENSHOT = re.compile(r"(?is)^screenshot(?:\s+(\S+))?$")


def parse_browser_host_command(line: str) -> dict[str, Any] | None:
    """
    Map imperative one-line browser commands to host_executor payloads.

    Requires host executor + Phase-14 browser flags (see :func:`_browser_host_commands_enabled`).
    """
    if not _browser_host_commands_enabled():
        return None
    s = (line or "").strip()
    if not s:
        return None

    m = _RE_BROWSER_OPEN.match(s) or _RE_BROWSER_NAV.match(s)
    if m:
        url = m.group(1).strip().rstrip(".,);]")
        if url:
            return {"host_action": "browser_open", "url": url}

    m = _RE_BROWSER_CLICK.match(s)
    if m:
        try:
            sel = _sanitize_selector(m.group(1))
        except ValueError:
            return None
        return {"host_action": "browser_click", "selector": sel}

    m = _RE_BROWSER_TYPE_INTO.match(s)
    if m:
        try:
            sel = _sanitize_selector(m.group(2))
        except ValueError:
            return None
        text = (m.group(1) or "").strip()
        if not text:
            return None
        return {"host_action": "browser_fill", "selector": sel, "text": text}

    m = _RE_BROWSER_SCREENSHOT.match(s)
    if m:
        name = (m.group(1) or "").strip() or None
        out: dict[str, Any] = {"host_action": "browser_screenshot"}
        if name:
            out["name"] = name
        return out

    return None


def _browser_host_commands_enabled() -> bool:
    s = get_settings()
    if not bool(getattr(s, "nexa_host_executor_enabled", False)):
        return False
    from app.services.browser.session import browser_phase14_allowed

    return bool(browser_phase14_allowed())
