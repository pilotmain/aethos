#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Run a one-shot web search using Nexa config (reads project .env). Does not print API keys.
  python scripts/verify_web_search.py "latest open source AI coding agents"
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure app loads repo .env the same way as the API
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Import after path — triggers config + dotenv
from app.core.config import get_settings  # noqa: E402
from app.services.web_search import (  # noqa: E402
    MissingWebSearchKey,
    WebSearchDisabled,
    format_search_results_for_prompt,
    search_web,
)


def main() -> int:
    if len(sys.argv) < 2 or not (sys.argv[1] or "").strip():
        print("Usage: python scripts/verify_web_search.py \"search query\"")
        return 2
    q = " ".join(sys.argv[1:]).strip()
    s = get_settings()
    prov = (s.nexa_web_search_provider or "none").lower()
    has_key = bool((s.nexa_web_search_api_key or "").strip())
    en = s.nexa_web_search_enabled
    print(f"NEXA_WEB_SEARCH_ENABLED={en!s}  provider={prov!r}  key_set={'yes' if has_key else 'no'}")
    if not en:
        print("verify_web_search: disabled (NEXA_WEB_SEARCH_ENABLED=false)")
        return 1
    if not has_key or prov in ("", "none"):
        print("verify_web_search: misconfigured (set NEXA_WEB_SEARCH_PROVIDER and NEXA_WEB_SEARCH_API_KEY)")
        return 1
    try:
        r = search_web(q)
    except WebSearchDisabled:
        print("verify_web_search: WebSearchDisabled")
        return 1
    except MissingWebSearchKey:
        print("verify_web_search: missing provider or key")
        return 1
    print(format_search_results_for_prompt(r)[:4_000])
    for i, it in enumerate(r.results, 1):
        print(f"{i}. {it.title[:80]!s}")
        print(f"   {it.url}")
    print("verify_web_search: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
