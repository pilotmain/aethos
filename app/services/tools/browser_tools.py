# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Browser automation hooks — gated by env + privacy (Phase 22)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings


def navigate_safe(url: str, *, user_id: str, db: Session | None = None) -> dict[str, Any]:
    """
    Placeholder for Playwright-driven navigation.

    When ``nexa_browser_preview_enabled`` is false, returns a structured refusal.
    """
    _ = user_id, db
    s = get_settings()
    if not s.nexa_browser_preview_enabled:
        return {
            "ok": False,
            "error": "browser_preview_disabled",
            "hint": "Set NEXA_BROWSER_PREVIEW_ENABLED=true after security review.",
        }
    return {
        "ok": False,
        "error": "browser_automation_not_installed",
        "url": (url or "")[:500],
    }


__all__ = ["navigate_safe"]
