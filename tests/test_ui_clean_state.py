# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 26 — lightweight UI source guards for legacy Nexa strings."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_suggestions_ts_no_legacy_dev_persona() -> None:
    text = (ROOT / "web/lib/suggestions.ts").read_text(encoding="utf-8")
    assert "@dev" not in text
    assert "@ops" not in text
