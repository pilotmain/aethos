"""Singleton async Playwright browser session (Phase 14)."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.core.config import get_settings

if TYPE_CHECKING:
    from playwright.async_api import Browser, Page, Playwright

logger = logging.getLogger(__name__)

_lock = asyncio.Lock()
_pw: Playwright | None = None
_browser: Browser | None = None


def browser_phase14_allowed() -> bool:
    s = get_settings()
    return bool(getattr(s, "nexa_browser_enabled", True)) or bool(
        getattr(s, "nexa_browser_automation_enabled", False),
    )


async def shutdown_browser_session() -> None:
    """Close Playwright browser (API shutdown)."""
    global _pw, _browser
    async with _lock:
        if _browser is not None:
            try:
                await _browser.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("browser close: %s", exc)
            _browser = None
        if _pw is not None:
            try:
                await _pw.stop()
            except Exception as exc:  # noqa: BLE001
                logger.debug("playwright stop: %s", exc)
            _pw = None


async def get_browser_page():
    """Return a shared Chromium page (lazy start)."""
    from playwright.async_api import async_playwright

    global _pw, _browser

    if not browser_phase14_allowed():
        raise RuntimeError("browser automation disabled (NEXA_BROWSER_ENABLED / automation flag)")

    async with _lock:
        s = get_settings()
        timeout_ms = int(getattr(s, "nexa_browser_timeout", 30000) or 30000)

        if _browser is not None:
            try:
                contexts = _browser.contexts
                if contexts and contexts[0].pages:
                    pg = contexts[0].pages[0]
                    if not pg.is_closed():
                        pg.set_default_timeout(timeout_ms)
                        return pg
            except Exception as exc:  # noqa: BLE001
                logger.warning("browser session stale, restarting: %s", exc)

            try:
                await _browser.close()
            except Exception:
                pass
            _browser = None
            if _pw is not None:
                try:
                    await _pw.stop()
                except Exception:
                    pass
                _pw = None

        _pw = await async_playwright().start()
        headless = bool(getattr(s, "nexa_browser_headless", True))
        _browser = await _pw.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
            ],
        )
        ctx = await _browser.new_context(
            user_agent=get_settings().nexa_web_user_agent or "AethOSBrowser/1.0",
        )
        page = await ctx.new_page()
        page.set_default_timeout(timeout_ms)
        logger.info("Phase 14 browser session started headless=%s", headless)
        return page


__all__ = ["browser_phase14_allowed", "get_browser_page", "shutdown_browser_session"]
