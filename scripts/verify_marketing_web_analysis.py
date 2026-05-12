#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Verify public URL read (and supplemental site: search when search is enabled) for marketing-style analysis.
Loads .env from the repo root; no LLM calls. Exits 1 if the public fetch has no usable text.

When NEXA_WEB_SEARCH_ENABLED is true, runs site:<host> products unless --no-search.
Usage:
  python scripts/verify_marketing_web_analysis.py https://pilotmain.com
  python scripts/verify_marketing_web_analysis.py pilotmain.com
  python scripts/verify_marketing_web_analysis.py pilotmain.com --no-search
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# repo root: scripts/ -> parent
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    p = _ROOT / ".env"
    if p.is_file():
        load_dotenv(p)


def main() -> int:
    _load_env()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("url", help="Public http(s) URL or bare host (e.g. pilotmain.com)")
    ap.add_argument(
        "--no-search",
        action="store_true",
        help="Skip supplemental web search even if NEXA_WEB_SEARCH_ENABLED is on.",
    )
    args = ap.parse_args()
    from app.core.config import get_settings
    from app.services.web_research_intent import build_marketing_search_query_against_url, extract_urls_from_text
    from app.services.web_access import summarize_public_page

    raw = (args.url or "").strip()
    urls = extract_urls_from_text(raw, max_urls=1)
    if not urls:
        print("Error: could not parse a resolvable public URL from:", raw, file=sys.stderr)
        return 1
    u = urls[0]
    s = get_settings()
    if not s.nexa_web_access_enabled:
        print("NEXA_WEB_ACCESS_ENABLED is false; public read is disabled.", file=sys.stderr)
        return 1
    sp = summarize_public_page(u, allow_internal=False)
    if not sp.ok and not (sp.text_excerpt or "").strip():
        err = (sp.user_message or sp.error or "fetch failed or empty").strip()
        print("Fetch failed:", err, file=sys.stderr)
        return 1
    title = (sp.title or "(no title)").strip()
    excerpt = (sp.text_excerpt or "")[:4_000]
    print("URL:", u)
    print("Title:", title)
    if not excerpt.strip():
        print("Error: no visible text excerpt from static read.", file=sys.stderr)
        return 1
    # Light heuristic: capitalized product-like tokens (not exhaustive)
    tokens = re.findall(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", excerpt)
    uniq: list[str] = []
    for w in tokens[:30]:
        if w not in uniq and len(w) > 2:
            uniq.append(w)
    if uniq:
        print("Product/service-like terms (heuristic):", ", ".join(uniq[:20]))
    else:
        print("Product/service-like terms: (none heuristically; see excerpt head below)")
    first_chunk = (excerpt[:1_200].strip() or "(empty)")
    print("First useful excerpt (head):")
    print(first_chunk)
    if len(excerpt) > 1_200:
        print("...")

    search_ran = False
    n_sources = 1
    search_status = "not run (no-search flag)"
    search_provider: str | None = None
    if not args.no_search and s.nexa_web_search_enabled:
        from app.services.web_search import search_web, WebSearchDisabled, MissingWebSearchKey

        q = build_marketing_search_query_against_url("", u)
        try:
            sr = search_web(q, requester_role=None)
            search_ran = True
            search_provider = sr.provider
            n_sources = 1 + len(sr.results or [])
            search_status = f"ok, provider={sr.provider}, results={len(sr.results or [])}"
            print("Search query:", q)
            print("Search results:", len(sr.results or []), f"(provider={sr.provider})")
            for i, r in enumerate((sr.results or [])[:5], 1):
                print(f"  {i}. {r.title or r.url} — {r.url}")
        except WebSearchDisabled:
            search_status = "skipped: WebSearchDisabled in runtime"
        except MissingWebSearchKey:
            search_status = "misconfigured: missing web search key/provider"
            print("Search skipped: provider or API key not configured.", file=sys.stderr)
    elif not args.no_search and not s.nexa_web_search_enabled:
        search_status = "skipped: NEXA_WEB_SEARCH_ENABLED=false"
    else:
        search_status = "skipped: --no-search"
    print("---")
    print("Search status:", search_status)
    if search_provider:
        print("Search provider:", search_provider)
    print("Supplemental search ran:", "yes" if search_ran else "no")
    print("Number of sources (page + search result URLs):", n_sources)
    print("OK: tool path for public read succeeded.")
    return 0


if __name__ == "__main__":
    os.chdir(_ROOT)
    raise SystemExit(main())
