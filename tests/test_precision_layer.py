# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 50 — response precision (dedupe + filler trim)."""

from __future__ import annotations

from app.services.response_humanization import enforce_precision


def test_enforce_precision_dedupes_paragraphs() -> None:
    t = "First line.\n\nFirst line.\n\nSecond line."
    out = enforce_precision(t)
    assert out.count("First line") == 1
    assert "Second line" in out


def test_enforce_precision_strips_filler() -> None:
    t = "Useful content here.\n\nI hope this helps."
    out = enforce_precision(t)
    assert "I hope this helps" not in out
    assert "Useful content" in out
