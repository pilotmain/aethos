# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 47D — workflow helpers for transient errors (unit-level)."""

from __future__ import annotations

from app.services.system_access import browser_playwright as bp


def test_transient_playwright_error_detects_timeout() -> None:
    assert bp._transient_playwright_error("Timeout 30000ms exceeded") is True


def test_navigation_error_hint() -> None:
    assert bp._navigation_error_hint("net::ERR_NAME_NOT_RESOLVED") is True
