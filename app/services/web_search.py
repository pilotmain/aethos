"""
Optional tool-based web search (Brave, Tavily, SerpAPI). Read-only: snippets + URLs only.
No scraping of result pages, no API keys in logs.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_REDACT = re.compile(
    r"(?i)(api_key|x-subscription-token|bearer|authorization|token)[=:]\s*['\"]?[^\s'\"&]+"
)


def _redact(s: str) -> str:
    t = s or ""
    t = _REDACT.sub(r"\1=(redacted)", t)
    return t[:1_200]


class WebSearchDisabled(Exception):
    def __str__(self) -> str:  # noqa: D105
        return "Web search is disabled (NEXA_WEB_SEARCH_ENABLED=false on the host)."


class MissingWebSearchKey(Exception):
    def __str__(self) -> str:  # noqa: D105
        return "Web search needs NEXA_WEB_SEARCH_PROVIDER and NEXA_WEB_SEARCH_API_KEY (see AethOS doctor)."


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source_provider: str


@dataclass
class SearchResponse:
    query: str
    provider: str
    results: list[SearchResult] = field(default_factory=list)


def _normalize_max_results() -> int:
    s = get_settings()
    n = int(s.nexa_web_search_max_results or 5)
    return min(max(1, n), 20)


def search_web(
    query: str,
    requester_role: str | None = None,  # noqa: ARG001 — reserved for policy
) -> SearchResponse:
    t = (query or "").strip()
    if not t:
        return SearchResponse(query="", provider="none", results=[])

    s = get_settings()
    if not s.nexa_web_search_enabled:
        logger.info("web_search: skipped (disabled in settings)")
        raise WebSearchDisabled()

    prov = (s.nexa_web_search_provider or "none").strip().lower()
    key = (s.nexa_web_search_api_key or "").strip()
    if prov in ("", "none", "off") or not key:
        logger.info("web_search: skipped (provider or key not configured)")
        raise MissingWebSearchKey()
    nmax = _normalize_max_results()

    if prov == "brave":
        return _search_brave(t, key, nmax)
    if prov == "tavily":
        return _search_tavily(t, key, nmax)
    if prov == "serpapi":
        return _search_serpapi(t, key, nmax)

    raise MissingWebSearchKey()


def _search_brave(query: str, token: str, nmax: int) -> SearchResponse:
    url = "https://api.search.brave.com/res/v1/web/search"
    out: list[SearchResult] = []
    prov = "brave"
    try:
        from app.services.safe_http_client import provider_get

        r = provider_get(
            url,
            params={"q": query, "count": nmax},
            headers={"X-Subscription-Token": token, "Accept": "application/json"},
            timeout=20.0,
        )
        r.raise_for_status()
        data = r.json() if r.content else {}
    except httpx.HTTPStatusError as e:  # noqa: BLE001
        err_body = (e.response.text or "")[:200]
        logger.info("brave search http error: %s", type(e).__name__, extra={"detail": _redact(err_body)})
        raise
    except Exception as e:  # noqa: BLE001
        logger.info("brave search failed: %s", type(e).__name__)
        raise
    # Brave: web.results
    results = (data or {}).get("web") or {}
    items = (results or {}).get("results") or []
    for it in items[:nmax] if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        u = (it.get("url") or "").strip()
        if not u or not u.startswith("http"):
            continue
        out.append(
            SearchResult(
                title=(it.get("title") or "result")[:500],
                url=u,
                snippet=(it.get("description") or it.get("title") or "")[:1500],
                source_provider=prov,
            )
        )
    return SearchResponse(query=query, provider=prov, results=out)


def _search_tavily(query: str, key: str, nmax: int) -> SearchResponse:
    prov = "tavily"
    out: list[SearchResult] = []
    try:
        from app.services.safe_http_client import provider_post

        r = provider_post(
            "https://api.tavily.com/search",
            json={
                "api_key": key,
                "query": query,
                "max_results": nmax,
            },
            headers={"Content-Type": "application/json"},
            timeout=25.0,
        )
        r.raise_for_status()
        data = r.json() if r.content else {}
    except httpx.HTTPStatusError as e:  # noqa: BLE001
        logger.info("tavily search http error: %s", e.response.status_code)
        raise
    except Exception as e:  # noqa: BLE001
        logger.info("tavily search failed: %s", type(e).__name__)
        raise
    items = (data or {}).get("results") or []
    for it in items[:nmax] if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        u = (it.get("url") or "").strip()
        if not u.startswith("http"):
            continue
        out.append(
            SearchResult(
                title=(it.get("title") or "result")[:500],
                url=u,
                snippet=(it.get("content") or it.get("raw_content") or "")[:1500],
                source_provider=prov,
            )
        )
    return SearchResponse(query=query, provider=prov, results=out)


def _search_serpapi(query: str, key: str, nmax: int) -> SearchResponse:
    prov = "serpapi"
    out: list[SearchResult] = []
    try:
        from app.services.safe_http_client import provider_get

        r = provider_get(
            "https://serpapi.com/search.json",
            params={
                "q": query,
                "api_key": key,
                "engine": "google",
            },
            timeout=25.0,
        )
        r.raise_for_status()
        data = r.json() if r.content else {}
    except httpx.HTTPStatusError as e:  # noqa: BLE001
        logger.info("serpapi search http error: %s", e.response.status_code)
        raise
    except Exception as e:  # noqa: BLE001
        logger.info("serpapi search failed: %s", type(e).__name__)
        raise
    org = (data or {}).get("organic_results") or []
    for it in org[:nmax] if isinstance(org, list) else []:
        if not isinstance(it, dict):
            continue
        u = (it.get("link") or it.get("url") or "").strip()
        if not u.startswith("http"):
            continue
        out.append(
            SearchResult(
                title=(it.get("title") or "result")[:500],
                url=u,
                snippet=(it.get("snippet") or it.get("title") or "")[:1500],
                source_provider=prov,
            )
        )
    return SearchResponse(query=query, provider=prov, results=out)


def format_search_results_for_prompt(
    response: SearchResponse, *, max_chars: int = 6_000
) -> str:
    """Inject into the LLM; not raw logs."""
    if not response.results:
        return f"Search returned no results. Query: {response.query!r} provider={response.provider}."
    lines: list[str] = [
        f"Search provider: {response.provider} (read-only, snippets and links only; do not open URLs in code).",
    ]
    for i, r in enumerate(response.results, 1):
        lines.append(
            f"--- Result {i} ---\n"
            f"Source: {r.url}\nTitle: {r.title}\nSnippet: {r.snippet}\n"
        )
    t = "\n\n".join(lines)[:max_chars]
    if _REDACT.sub("", t) != t:  # defensive
        t = _REDACT.sub("…", t)
    return t


def extract_user_search_query_for_intent(
    user_text: str, *, is_research_mention: bool = False
) -> str:
    """
    Strip @research prefix and common 'search the web' phrases; keep the topic to search.
    """
    t = (user_text or "").strip()
    if is_research_mention:
        t = re.sub(r"^\s*@research\s+", "", t, flags=re.I)
    t = re.sub(r"^\s*@marketing\s+", "", t, flags=re.I)
    t = re.sub(
        r"^\s*search\s+the\s+web\s+for\s*",
        "",
        t,
        flags=re.I,
    )
    t = re.sub(
        r"^\s*web\s+search\s*:\s*",
        "",
        t,
        flags=re.I,
    )
    return t.strip()[:1_200] or (user_text or "").strip()[:1_200]
