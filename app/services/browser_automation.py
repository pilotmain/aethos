# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Host-executor browser helpers: URL allowlist + sync bridge to async Playwright."""

from __future__ import annotations

import asyncio
import concurrent.futures
import re
from typing import Any
from urllib.parse import urlparse

from app.core.config import get_settings


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


def run_browser_host_action_sync(action: str, payload: dict[str, Any]) -> str:
    """
    Run a allowlisted browser host_action from synchronous :func:`~app.services.host_executor.execute_payload`.

    ``action`` is one of: ``browser_open``, ``browser_click``, ``browser_fill``, ``browser_screenshot``.
    """
    from app.services.browser.controller import get_browser_controller

    act = (action or "").strip().lower()
    ctrl = get_browser_controller()
    timeout_ms = default_browser_timeout_ms()
    op_timeout = min(max(timeout_ms, 1000), 120_000)

    async def _run() -> str:
        if act == "browser_open":
            url = str(payload.get("url") or "").strip()
            if not url:
                raise ValueError("browser_open requires url")
            assert_browser_url_allowed(url)
            r = await ctrl.navigate(url, wait_until="domcontentloaded")
            if not r.success:
                raise ValueError(r.error or "navigate failed")
            return str(r.output)
        if act == "browser_click":
            sel = _sanitize_selector(str(payload.get("selector") or ""))
            r = await ctrl.click(sel, timeout=op_timeout)
            if not r.success:
                raise ValueError(r.error or "click failed")
            return str(r.output)
        if act == "browser_fill":
            sel = _sanitize_selector(str(payload.get("selector") or ""))
            text = str(payload.get("text") or "")
            if not text:
                raise ValueError("browser_fill requires text")
            if len(text) > 50_000:
                raise ValueError("text too long (max 50000)")
            r = await ctrl.fill(sel, text, timeout=op_timeout)
            if not r.success:
                raise ValueError(r.error or "fill failed")
            return str(r.output)
        if act == "browser_screenshot":
            name = str(payload.get("name") or "").strip() or None
            r = await ctrl.screenshot(name)
            if not r.success:
                raise ValueError(r.error or "screenshot failed")
            return str(r.output)
        raise ValueError(f"unknown browser host action {act!r}")

    async def _wrapper() -> str:
        return await _run()

    wall_timeout = min(600, max(30, op_timeout // 1000 + 30))

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_wrapper())
    else:

        def _thread_runner() -> str:
            return asyncio.run(_wrapper())

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_thread_runner).result(timeout=wall_timeout)


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
