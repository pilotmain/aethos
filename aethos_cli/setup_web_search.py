# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Web search provider setup (Phase 4 Step 4)."""

from __future__ import annotations

from typing import Any

from aethos_cli.setup_secrets import safe_token_confirm_display
from aethos_cli.ui import get_input, print_info, print_warn

PROVIDERS = (
    ("Brave Search", "brave", "BRAVE_SEARCH_API_KEY"),
    ("Tavily", "tavily", "TAVILY_API_KEY"),
    ("Exa", "exa", "EXA_API_KEY"),
    ("Perplexity", "perplexity", "PERPLEXITY_API_KEY"),
    ("Skip", "skip", None),
)


def configure_web_search(choice: str, updates: dict[str, str]) -> dict[str, Any]:
    for _label, slug, env_key in PROVIDERS:
        if slug != choice:
            continue
        if env_key is None:
            return {"provider": "skip", "configured": False}
        key = get_input(f"{env_key}", hide=True)
        if not key.strip():
            print_warn("Skipped web search provider.")
            return {"provider": slug, "configured": False}
        updates[env_key] = key.strip()
        updates["AETHOS_WEB_SEARCH_PROVIDER"] = slug
        print_info(safe_token_confirm_display(key))
        return {"provider": slug, "configured": True}
    return {"provider": "unknown", "configured": False}
