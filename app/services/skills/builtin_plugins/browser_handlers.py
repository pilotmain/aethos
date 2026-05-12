# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Built-in Phase 14 browser plugin skill handlers (async)."""

from __future__ import annotations

from typing import Any

from app.services.browser.controller import BrowserActionResult, get_browser_controller
from app.services.browser.session import browser_phase14_allowed


def _to_dict(r: BrowserActionResult) -> dict[str, Any]:
    out: dict[str, Any] = {"success": r.success, "output": r.output}
    if r.error:
        out["error"] = r.error
    if r.screenshot_path:
        out["screenshot_path"] = r.screenshot_path
    return out


async def browser_navigate(url: str, wait_until: str = "domcontentloaded") -> dict[str, Any]:
    if not browser_phase14_allowed():
        return {"success": False, "error": "browser_disabled", "output": None}
    ctrl = get_browser_controller()
    return _to_dict(await ctrl.navigate(url, wait_until=wait_until))


async def browser_click(selector: str) -> dict[str, Any]:
    if not browser_phase14_allowed():
        return {"success": False, "error": "browser_disabled", "output": None}
    ctrl = get_browser_controller()
    return _to_dict(await ctrl.click(selector))


async def browser_fill(selector: str, value: str) -> dict[str, Any]:
    if not browser_phase14_allowed():
        return {"success": False, "error": "browser_disabled", "output": None}
    ctrl = get_browser_controller()
    return _to_dict(await ctrl.fill(selector, value))


async def browser_get_text(selector: str) -> dict[str, Any]:
    if not browser_phase14_allowed():
        return {"success": False, "error": "browser_disabled", "output": None}
    ctrl = get_browser_controller()
    return _to_dict(await ctrl.get_text(selector))


async def browser_get_html(selector: str | None = None) -> dict[str, Any]:
    if not browser_phase14_allowed():
        return {"success": False, "error": "browser_disabled", "output": None}
    ctrl = get_browser_controller()
    return _to_dict(await ctrl.get_html(selector))


async def browser_screenshot(name: str | None = None, full_page: bool = True) -> dict[str, Any]:
    if not browser_phase14_allowed():
        return {"success": False, "error": "browser_disabled", "output": None}
    ctrl = get_browser_controller()
    return _to_dict(await ctrl.screenshot(name, full_page=full_page))


async def browser_evaluate(script: str) -> dict[str, Any]:
    if not browser_phase14_allowed():
        return {"success": False, "error": "browser_disabled", "output": None}
    ctrl = get_browser_controller()
    return _to_dict(await ctrl.evaluate(script))


__all__ = [
    "browser_click",
    "browser_evaluate",
    "browser_fill",
    "browser_get_html",
    "browser_get_text",
    "browser_navigate",
    "browser_screenshot",
]
