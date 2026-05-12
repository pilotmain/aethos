# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 38 — token counter stability."""

from __future__ import annotations

from app.services.token_economy.counter import estimate_payload_tokens, estimate_tokens


def test_estimate_tokens_minimum_one() -> None:
    assert estimate_tokens("") == 1
    assert estimate_tokens("abcd") == 1


def test_estimate_tokens_scales_with_length() -> None:
    s = "word " * 400
    assert estimate_tokens(s) == len(s) // 4


def test_estimate_payload_tokens_stable() -> None:
    pl = {"task": "hello", "tool": "research", "agent": "A"}
    a = estimate_payload_tokens(pl)
    b = estimate_payload_tokens(pl)
    assert a == b
    assert a >= 1
