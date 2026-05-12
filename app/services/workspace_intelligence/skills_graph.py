# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Lightweight skill-chain hints from natural-language goals (keyword-based)."""

from __future__ import annotations

import re

# Ordered chains: content / growth workflows (extensible without a DB).
_CHAINS: list[tuple[re.Pattern[str], list[str]]] = [
    (
        re.compile(
            r"(?i)(linkedin).*(post|article)|(post|article).*(linkedin)|podcast.*linkedin|transcript.*linkedin"
        ),
        ["transcript", "hook_finder", "script_writer", "caption_generator"],
    ),
    (
        re.compile(r"(?i)newsletter|seo article|blog post"),
        ["hook_finder", "script_writer"],
    ),
    (
        re.compile(r"(?i)transcript|podcast|episode"),
        ["transcript", "hook_finder", "script_writer"],
    ),
    (
        re.compile(r"(?i)cold outreach|sequence|email campaign"),
        ["hook_finder", "script_writer"],
    ),
]


def find_skill_chain(goal: str) -> list[str]:
    """
    Return a deduplicated skill id chain suggested for ``goal``.

    Uses substring / regex only — no GPU, no vector DB.
    """
    g = (goal or "").strip()
    if not g:
        return []
    for pat, chain in _CHAINS:
        if pat.search(g):
            return list(dict.fromkeys(chain))
    return []


__all__ = ["find_skill_chain"]
