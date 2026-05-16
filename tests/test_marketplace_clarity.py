# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path


def test_marketplace_clarity_copy() -> None:
    text = Path("web/app/mission-control/(shell)/marketplace/page.tsx").read_text(encoding="utf-8")
    assert "Runtime plugin" in text
    assert "Automation pack" in text
    assert "Marketplace skill" in text
