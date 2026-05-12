# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Async Playwright controller (Chromium / CDP-style automation, Phase 14)."""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.browser.session import browser_phase14_allowed, get_browser_page

logger = logging.getLogger(__name__)


@dataclass
class BrowserActionResult:
    success: bool
    output: Any
    error: str | None = None
    screenshot_path: str | None = None


class BrowserController:
    """Thin facade over a shared Playwright page."""

    async def _page(self):
        if not browser_phase14_allowed():
            raise RuntimeError("browser automation disabled")
        return await get_browser_page()

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> BrowserActionResult:
        try:
            page = await self._page()
            await page.goto(url, wait_until=wait_until)
            title = await page.title()
            return BrowserActionResult(success=True, output=f"Navigated to {url}\nTitle: {title}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("navigate failed")
            return BrowserActionResult(success=False, output=None, error=str(exc))

    async def click(self, selector: str, timeout: int | None = None) -> BrowserActionResult:
        try:
            page = await self._page()
            await page.click(selector, timeout=timeout)
            return BrowserActionResult(success=True, output=f"Clicked: {selector}")
        except Exception as exc:  # noqa: BLE001
            return BrowserActionResult(success=False, output=None, error=str(exc))

    async def fill(self, selector: str, value: str, timeout: int | None = None) -> BrowserActionResult:
        try:
            page = await self._page()
            await page.fill(selector, value, timeout=timeout)
            return BrowserActionResult(success=True, output=f"Filled {selector}")
        except Exception as exc:  # noqa: BLE001
            return BrowserActionResult(success=False, output=None, error=str(exc))

    async def type_text(self, selector: str, text: str, delay: int = 50) -> BrowserActionResult:
        try:
            page = await self._page()
            await page.type(selector, text, delay=delay)
            return BrowserActionResult(success=True, output=f"Typed into {selector}")
        except Exception as exc:  # noqa: BLE001
            return BrowserActionResult(success=False, output=None, error=str(exc))

    async def select_option(self, selector: str, value: str) -> BrowserActionResult:
        try:
            page = await self._page()
            await page.select_option(selector, value)
            return BrowserActionResult(success=True, output=f"Selected {value} on {selector}")
        except Exception as exc:  # noqa: BLE001
            return BrowserActionResult(success=False, output=None, error=str(exc))

    async def get_text(self, selector: str) -> BrowserActionResult:
        try:
            page = await self._page()
            text = await page.text_content(selector)
            return BrowserActionResult(success=True, output=(text or "").strip())
        except Exception as exc:  # noqa: BLE001
            return BrowserActionResult(success=False, output=None, error=str(exc))

    async def get_html(self, selector: str | None = None) -> BrowserActionResult:
        try:
            page = await self._page()
            if selector:
                element = await page.query_selector(selector)
                if not element:
                    return BrowserActionResult(success=False, output=None, error=f"Element not found: {selector}")
                html = await element.inner_html()
            else:
                html = await page.content()
            return BrowserActionResult(success=True, output=html)
        except Exception as exc:  # noqa: BLE001
            return BrowserActionResult(success=False, output=None, error=str(exc))

    async def screenshot(self, name: str | None = None, *, full_page: bool = True) -> BrowserActionResult:
        settings = get_settings()
        screenshot_dir = Path(settings.nexa_browser_screenshot_dir or "")
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        stem = name or f"screenshot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
        if not str(stem).lower().endswith(".png"):
            stem = f"{stem}.png"
        path = screenshot_dir / stem
        try:
            page = await self._page()
            await page.screenshot(path=str(path), full_page=full_page)
            return BrowserActionResult(success=True, output=f"Screenshot saved: {path}", screenshot_path=str(path))
        except Exception as exc:  # noqa: BLE001
            return BrowserActionResult(success=False, output=None, error=str(exc))

    async def screenshot_base64(self, *, full_page: bool = True) -> BrowserActionResult:
        try:
            page = await self._page()
            blob = await page.screenshot(full_page=full_page)
            b64 = base64.b64encode(blob).decode()
            return BrowserActionResult(success=True, output=b64)
        except Exception as exc:  # noqa: BLE001
            return BrowserActionResult(success=False, output=None, error=str(exc))

    async def pdf(self, path: str | None = None) -> BrowserActionResult:
        settings = get_settings()
        out_dir = Path(settings.nexa_browser_screenshot_dir or "")
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = path or f"page_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
        if not stem.lower().endswith(".pdf"):
            stem = f"{stem}.pdf"
        dest = out_dir / stem
        try:
            page = await self._page()
            await page.pdf(path=str(dest))
            return BrowserActionResult(success=True, output=str(dest), screenshot_path=str(dest))
        except Exception as exc:  # noqa: BLE001
            return BrowserActionResult(success=False, output=None, error=str(exc))

    async def wait_for_selector(self, selector: str, timeout: int | None = None) -> BrowserActionResult:
        try:
            page = await self._page()
            await page.wait_for_selector(selector, timeout=timeout)
            return BrowserActionResult(success=True, output=f"Element appeared: {selector}")
        except Exception as exc:  # noqa: BLE001
            return BrowserActionResult(success=False, output=None, error=str(exc))

    async def wait_for_navigation(self, timeout: int | None = None) -> BrowserActionResult:
        try:
            page = await self._page()
            await page.wait_for_load_state("domcontentloaded", timeout=timeout)
            return BrowserActionResult(success=True, output="Load settled")
        except Exception as exc:  # noqa: BLE001
            return BrowserActionResult(success=False, output=None, error=str(exc))

    async def evaluate(self, script: str) -> BrowserActionResult:
        try:
            page = await self._page()
            result = await page.evaluate(script)
            try:
                out = json.dumps(result, ensure_ascii=False, default=str)
            except TypeError:
                out = str(result)
            return BrowserActionResult(success=True, output=out)
        except Exception as exc:  # noqa: BLE001
            return BrowserActionResult(success=False, output=None, error=str(exc))

    async def scroll_to(self, selector: str | None = None, *, x: int = 0, y: int = 0) -> BrowserActionResult:
        try:
            page = await self._page()
            if selector:
                loc = page.locator(selector).first
                await loc.scroll_into_view_if_needed()
            else:
                await page.evaluate(f"window.scrollTo({x}, {y})")
            return BrowserActionResult(success=True, output=f"Scrolled {selector or f'({x},{y})'}")
        except Exception as exc:  # noqa: BLE001
            return BrowserActionResult(success=False, output=None, error=str(exc))

    async def go_back(self) -> BrowserActionResult:
        try:
            page = await self._page()
            await page.go_back()
            return BrowserActionResult(success=True, output="Went back")
        except Exception as exc:  # noqa: BLE001
            return BrowserActionResult(success=False, output=None, error=str(exc))

    async def close_extra_tabs(self, *, keep_first: bool = True) -> BrowserActionResult:
        try:
            page = await self._page()
            browser = page.context.browser
            if browser is None:
                return BrowserActionResult(success=True, output="No browser")
            for ctx in browser.contexts:
                pages = ctx.pages
                for i, pg in enumerate(pages):
                    if keep_first and i == 0:
                        continue
                    await pg.close()
            return BrowserActionResult(success=True, output="Closed extra tabs")
        except Exception as exc:  # noqa: BLE001
            return BrowserActionResult(success=False, output=None, error=str(exc))


_singleton: BrowserController | None = None


def get_browser_controller() -> BrowserController:
    global _singleton
    if _singleton is None:
        _singleton = BrowserController()
    return _singleton


__all__ = ["BrowserActionResult", "BrowserController", "get_browser_controller"]
