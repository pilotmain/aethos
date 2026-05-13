# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Optional browser slice — not part of ``-m product_e2e`` (separate marker)."""

from __future__ import annotations

import os

import pytest


@pytest.mark.product_e2e_browser
@pytest.mark.skipif(
    not (os.environ.get("RUN_BROWSER_E2E") or "").strip().lower() in ("1", "true", "yes"),
    reason="Set RUN_BROWSER_E2E=1 to enable browser slice (requires playwright in env)",
)
def test_playwright_chromium_import() -> None:
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        assert p.chromium is not None
