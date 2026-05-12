# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Prompt budget tiers for main chat — reduce input tokens on simple turns."""

from __future__ import annotations

import re


def classify_prompt_budget_tier(
    user_message: str,
    *,
    intent: str | None = None,
) -> int:
    """
    Tier 0 — ultra-light (minimal system + slim user JSON). Short factual / identity.
    Tier 1 — compact persona + small context (no full BASE_SYSTEM_PROMPT).
    Tier 2 — full composer (tools, host, memory blocks, long rules).
    """
    u = (user_message or "").strip()
    if not u:
        return 2
    if "\n" in u or len(u) > 700:
        return 2
    # Host / path / tool signals need full guidance
    if re.search(
        r"(?i)(/users/|/home/|~/|\blist\s+files?\b|\bls\b|\bread\s+file\b|\bwrite\b|"
        r"\bpytest\b|\bgit\s+status\b|@dev|@marketing|@research|http://|https://)",
        u,
    ):
        return 2
    low = u.lower()
    if intent in ("capability_question", "brain_dump"):
        return 2
    # Short identity / product questions (non-canned fallthrough)
    if len(u) < 140 and re.match(
        r"(?i)^(who|what|when|where|why|how)\s+(is|are|was|were|do|does|did|can)\s+",
        u,
    ):
        return 0
    if len(u) < 100 and re.match(r"(?i)^(hi|hello|hey|thanks|thank you|ok|okay)\b", low):
        return 1
    if len(u) < 200:
        return 1
    return 2
