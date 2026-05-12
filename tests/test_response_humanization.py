# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 49 — response humanization and length bounds."""

from __future__ import annotations

from app.services.response_formatter import finalize_user_facing_text
from app.services.response_humanization import humanize_response, minimize_response_length


def test_humanize_strips_opening_clichés() -> None:
    t = "As an AI language model, I can help you plan your day."
    h = humanize_response(t)
    assert "As an AI" not in h
    assert "plan" in h.lower()

    t2 = "I'm an AI assistant. Here is the answer."
    assert "I'm an AI" not in humanize_response(t2)

    t3 = "Based on the context you've provided.\n\nTake a breath first."
    h3 = humanize_response(t3)
    assert not h3.strip().lower().startswith("based on")

    t4 = "a\n\n\n\n\nb"
    h4 = humanize_response(t4)
    assert "\n\n\n\n" not in h4


def test_minimize_truncates_with_ellipsis() -> None:
    long = "x" * 20000
    m = minimize_response_length(long, max_chars=100)
    assert len(m) <= 102
    assert m.endswith("…")


def test_finalize_applies_humanization_pipeline() -> None:
    raw = "As an AI assistant,\n\nHello."
    out = finalize_user_facing_text(raw, user_preferences=None)
    assert "As an AI assistant" not in out
