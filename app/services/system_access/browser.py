# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Browser automation gate — use Mission Control / Playwright paths when enabled (Phase 39 stub)."""

from __future__ import annotations

from typing import Any


def browse_url_placeholder(url: str, *, enabled: bool = False) -> dict[str, Any]:
    """Placeholder until Playwright preview is wired for autonomous browsing."""
    if not enabled:
        return {"ok": False, "error": "browser_disabled", "url": url[:500]}
    return {"ok": False, "error": "not_implemented", "url": url[:500]}


__all__ = ["browse_url_placeholder"]
