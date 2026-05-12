# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Canonical action_type values for LLM usage analytics.
"""

from __future__ import annotations

# Allowed primary labels (per product spec)
CHAT_RESPONSE = "chat_response"
INTENT_CLASSIFICATION = "intent_classification"
WEB_SEARCH_SUMMARY = "web_search_summary"
PUBLIC_URL_SUMMARY = "public_url_summary"
PLAN_REFINEMENT = "plan_refinement"
MEMORY_RESPONSE = "memory_response"

CANONICAL: frozenset[str] = frozenset(
    {
        CHAT_RESPONSE,
        INTENT_CLASSIFICATION,
        WEB_SEARCH_SUMMARY,
        PUBLIC_URL_SUMMARY,
        PLAN_REFINEMENT,
        MEMORY_RESPONSE,
    }
)

_ALIASES: dict[str, str] = {
    "public_web_summary": PUBLIC_URL_SUMMARY,
}


def normalize_action_type(name: str | None) -> str:
    s = (name or "").strip()
    if not s:
        return CHAT_RESPONSE
    s = _ALIASES.get(s, s)
    if s in CANONICAL:
        return s
    return CHAT_RESPONSE
