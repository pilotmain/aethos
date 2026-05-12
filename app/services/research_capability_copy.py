# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""User-facing copy for research / public web / live search (runtime from settings)."""

from __future__ import annotations

import re

from app.core.config import get_settings


def is_research_capability_question(text: str) -> bool:
    """True when the user is asking about web research, search, or browsing (not a command list)."""
    t = (text or "").strip().lower()
    if not t or len(t) > 500:
        return False
    if re.search(
        r"\b(/help|/command|/agents|list commands|what commands)\b",
        t,
    ):
        return False
    phrase_hits = (
        "web research",
        "internet research",
        "search the web",
        "search online",
        "web search",
        "live search",
        "google",
        "browse the web",
        "browse the internet",
        "browsing the web",
        "live web",
        "look things up online",
        "do you have access to the web",
        "can you access the web",
        "can you use google",
        "search the internet",
        "can you research online",
    )
    if any(p in t for p in phrase_hits):
        return True
    if "do you have" in t and any(
        x in t for x in ("web", "google", "internet", "search", "browse")
    ):
        return True
    if "can you" in t and any(
        x in t
        for x in (
            "search the web",
            "use google",
            "browse",
            "internet",
        )
    ):
        return True
    return False


def _line_public_url() -> str:
    s = get_settings()
    on = bool(s.nexa_web_access_enabled)
    return "Public URL reading: **enabled**" if on else "Public URL reading: **disabled**"


def _line_web_search() -> str:
    s = get_settings()
    if not s.nexa_web_search_enabled:
        return "Web search: **disabled** (live search is off; paste a public URL for read-only page text)"
    prov = (s.nexa_web_search_provider or "none").lower().strip() or "none"
    key = bool((s.nexa_web_search_api_key or "").strip())
    if prov in ("brave", "tavily", "serpapi") and key:
        return f"Web search: **enabled** ({prov})"
    return (
        "Web search: **disabled** (set `NEXA_WEB_SEARCH_ENABLED=true` plus provider and "
        "`NEXA_WEB_SEARCH_API_KEY` on the host; then restart the API and bot)"
    )


def _line_browser_preview() -> str:
    s = get_settings()
    on = bool(s.nexa_browser_preview_enabled)
    return (
        "Browser preview: **enabled** (owner, optional)"
        if on
        else "Browser preview: **disabled** (optional, owner-only)"
    )


def format_research_capability_message() -> str:
    """Explains public URL read vs live search vs browser preview from current config."""
    return (
        "Research capability:\n\n"
        "• I can read **public http(s) pages** when you paste a link in chat.\n"
        "• **Live web search** (query → snippets and links) is available only when the host sets "
        "`NEXA_WEB_SEARCH_ENABLED=true` and a **search provider API key** (Brave, Tavily, or SerpAPI). "
        "The API and bot must be restarted after changing env.\n"
        "• **Browser preview** (optional Playwright) is **owner-only** and off unless enabled.\n\n"
        "Current status:\n\n"
        f"• {_line_public_url()}\n"
        f"• {_line_web_search()}\n"
        f"• {_line_browser_preview()}\n"
    )
