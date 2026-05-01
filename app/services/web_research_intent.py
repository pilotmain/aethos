"""
Detect public URLs in user text and resolve role for web-access policy (SSRF, internal).
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.telegram_link import TelegramLink
from app.services.app_user_id_parse import parse_telegram_id_from_app_user_id
from app.services.user_capabilities import get_telegram_role, is_owner_role

# https://... and common bare host.TLD (incl. www. and other subdomains)
_TLD = (
    "com|org|net|io|app|dev|ai|co|us|me|ly|cc|tech|so|sh|to|gg|tv|"
    "cloud|pro|work|land|info|name|one|io"
)
# Single- or multi-label host: pilotmain.com, www.pilotmain.com, app.sub.example.com
# Group 0 is the full match; (?:%s) is the TLD.
_BARE = (
    r"(?i)(?<!@)"
    r"(?<![/])"  # avoid "path/segment.com" edge cases; https:// handled separately
    r"\b"
    r"((?:(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)\.)*"
    r"([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))\.(?!:)(%s)(?:/[^\s<>\'\"`]+)?" % f"(?:{_TLD})"
    r"(?![a-z0-9.-])"  # don't eat into a longer host mid-token
)
_RE_HTTPS = re.compile(r"https?://[^\s<>\'\"`]+", re.I)
_RE_BARE = re.compile(_BARE)


def _normalize_url(raw: str) -> str:
    t = (raw or "").strip().rstrip(").,;]\"'")
    if t.lower().startswith("http://") or t.lower().startswith("https://"):
        return t
    if "://" in t:
        return t
    if "/" in t and not t.startswith("/"):
        return f"https://{t.split()[0]}"
    if re.match(r"^[\w.-]+\.\w{2,}$", t, re.I):
        return f"https://{t}"
    return t


def extract_urls_from_text(s: str, *, max_urls: int = 3) -> list[str]:
    t = (s or "").strip()
    if not t:
        return []
    seen: set[str] = set()
    out: list[str] = []

    def _push(u0: str) -> bool:
        nonlocal out, seen
        n = _normalize_url(u0)
        p2 = urlparse(n)
        if p2.scheme not in ("http", "https") or not p2.hostname:
            return False
        if n in seen:
            return True
        if len(out) >= max_urls:
            return True
        seen.add(n)
        out.append(n)
        return len(out) >= max_urls

    for m in _RE_HTTPS.finditer(t):
        if _push(m.group(0)):
            return out
    # Do not re-match host.tld that is part of a longer http(s) URL
    t_masked = list(t)
    for m in _RE_HTTPS.finditer(t):
        for j in range(m.start(), m.end()):
            if j < len(t_masked):
                t_masked[j] = " "
    t2 = "".join(t_masked)
    for m in _RE_BARE.finditer(t2):
        if _push(m.group(0)):
            return out
    return out


def app_user_allows_internal_fetch(db: Session, app_user_id: str) -> bool:
    """Only owner may fetch private / internal hosts (e.g. RFC1918) when policy allows."""
    tid = parse_telegram_id_from_app_user_id(app_user_id)
    if tid is not None:
        return is_owner_role(get_telegram_role(tid, db))
    # Web UI / API with non-telegram id: never allow internal
    if not (app_user_id or "").strip():
        return False
    row = db.scalars(
        select(TelegramLink).where(TelegramLink.app_user_id == (app_user_id or "").strip())
    ).first()
    if row is None:
        return False
    return is_owner_role(get_telegram_role(int(row.telegram_user_id), db))


# "browser preview https://…" (owner-only in handler)
_BROWSER_PREVIEW_PHRASE = re.compile(
    r"(?i)\b(browser\s+preview|preview\s+with\s+browser|render\s+in\s+browser)\b"
)

# Message is almost only a host/URL (user pasted a site to open)
_BARE_URL_ONLY = re.compile(
    r"^\s*(?:(?:https?://)\S+|[\w](?:[.\w-])+\.[\w-]{2,})(?:/[^\s]*)?/?\s*$", re.IGNORECASE
)


def extract_url_for_browser_preview(text: str) -> str | None:
    """If user asked for a browser/preview and included a public URL, return the first URL."""
    t = (text or "").strip()
    if not t or not _BROWSER_PREVIEW_PHRASE.search(t):
        return None
    u = extract_urls_from_text(t, max_urls=1)
    return u[0] if u else None


# Web search: strong / weak signals (Phase 2; tool-based, not "random browse")
_STRONG_SEARCH = re.compile(
    r"(?i)\b("
    r"search\s+the\s+web|"
    r"web\s+search|"
    r"find\s+information\s+about|"
    r"what\s+are\s+people\s+saying|"
    r"news\s+about|"
    r"compare\s+companies|"
    r"look\s+it\s+up|"
    r"look\s+up(?=\s+)"
    r")\b"
)
# "compare X and Y" for products (not every "compare" in a sentence)
_COMPARE_PRODUCTS = re.compile(
    r"(?i)\bcompare\s+[\w.+\- ]{2,64}\s+(and|vs\.?|versus)\s+"
)
_TIMEISH = re.compile(
    r"(?i)\b("
    r"latest|current|recent|today|this\s+week|this\s+month|"
    r"right\s+now|202[4-9]|as\s+of|breaking"
    r")\b"
)
_RESEARCH_TOPIC = re.compile(
    r"(?i)\b("
    r"research\s+(on|into|about|the)|"
    r"investigate|survey|market\s+scan|"
    r"any\s+news|what\s+is\s+the\s+consensus|"
    r"find\s+sources|find\s+articles"
    r")\b"
)
_MARKETING_URL_TOOL_PHRASES = re.compile(
    r"(?i)\b("
    r"website|web\s+site|\bsite\b|on\s+the\s+site|on\s+this\s+site|on\s+that\s+site|"
    r"public\s+site|our\s+site|their\s+site|"
    r"web\s+search|search\s+the\s+web|"
    r"product(?:s|)\s+list|our\s+products|the\s+products|summar(?:y|ies)\s+of\s+products|"
    r"research\s+this\s+compan(?:y|ies)|how\s+can\s+we\s+market|"
    r"positioning|landing\s*page|home\s*page|linkedin"
    r")\b"
)
# Used when deciding whether a marketing request should be grounded with tools (with a URL present)
_MARKETING_WEB_SIGNAL = re.compile(
    r"(?i)\b("
    r"product(?:s|)\b|services?|offering|website|web\s*site|domain|url|http|www\.|"
    r"web\s+search|search\s+the\s+web|look\s*up|market(ing|)|positioning|"
    r"summar(?:e|y|ies)\b|research|company|competitor|landing|homepage|linkedin|"
    r"latest|current|today"
    r")"
)


def primary_registrable_host_for_url(url: str) -> str:
    """
    Returns hostname (lowercase) for search queries, stripping a leading "www."
    """
    h = (urlparse(url).hostname or "").strip().lower()
    if h.startswith("www."):
        return h[4:]
    return h


def build_marketing_search_query_against_url(user_text: str, primary_url: str | None) -> str:
    """
    Focused query when marketing already has a resolvable public URL. Prefer site: so
    the provider can merge with static fetch in the same turn.
    """
    t = (user_text or "").strip()[:1_200]
    u = (primary_url or "").strip()
    h = primary_registrable_host_for_url(u) if u else ""
    if h:
        return f"site:{h} products"
    return t


def marketing_mentions_website_or_research_phrase(text: str) -> bool:
    """Heuristic: user is asking to analyze a site, products, or do web research for copy."""
    t = (text or "").strip()
    if not t:
        return False
    return bool(_MARKETING_URL_TOOL_PHRASES.search(t))


def marketing_message_mentions_web_research_intent_with_url(user_text: str) -> bool:
    """With at least one extracted URL, True when the message is likely a site/product ask."""
    t = (user_text or "").strip()
    if not t or not extract_urls_from_text(t, max_urls=1):
        return False
    return bool(_MARKETING_WEB_SIGNAL.search(t))


def _looks_like_dev_or_ops_command(text: str) -> bool:
    t = (text or "").strip()
    if re.match(r"^/(\s*)(dev|ops|job|memory|agents|context|improve|learning|start|help)\b", t, re.I):
        return True
    if re.match(r"^@(\s*)(dev|ops)\b", t, re.I):
        return True
    return False


def web_search_intent_heuristic(text: str) -> bool:
    """
    Raw intent signals for live web search (no orchestrator suppression).

    Routing uses this directly so ``should_suppress_public_web_pipeline`` →
    ``build_routing_context`` does not recurse into ``should_use_web_search``.
    """
    t = (text or "").strip()
    if len(t) < 4:
        return False
    if _looks_like_dev_or_ops_command(t):
        return False
    if should_use_public_url_read(t) and extract_urls_from_text(t, max_urls=1):
        return False
    if extract_url_for_browser_preview(t):
        return False
    if _STRONG_SEARCH.search(t) or _COMPARE_PRODUCTS.search(t) or _RESEARCH_TOPIC.search(t):
        return True
    if _TIMEISH.search(t) and len(t) > 12:
        return True
    return bool(re.search(r"(?i)\blook\s+up\b", t) and len(t) > 15)


def should_use_web_search(text: str) -> bool:
    """
    True when the user likely wants live web search (not direct URL read, not dev/ops).
    Direct URL read and browser preview take priority (caller order).
    """
    t = (text or "").strip()
    from app.services.routing.authority import should_suppress_public_web_pipeline

    if should_suppress_public_web_pipeline(t):
        return False
    return web_search_intent_heuristic(t)


def should_use_marketing_supplemental_web_search(text: str) -> bool:
    """
    When @marketing fetches a public page, live web search is usually skipped so we
    do not duplicate work. If the user explicitly asked for a web search (or other
    search-like intent), or there is no "URL read takes priority" conflict, we may
    add search to the same marketing turn.
    """
    t = (text or "").strip()
    if len(t) < 4:
        return False
    if _looks_like_dev_or_ops_command(t):
        return False
    if extract_url_for_browser_preview(t):
        return False
    if (
        _STRONG_SEARCH.search(t)
        or _RESEARCH_TOPIC.search(t)
        or _COMPARE_PRODUCTS.search(t)
        or (_TIMEISH.search(t) and len(t) > 12)
        or (re.search(r"(?i)\blook\s+up\b", t) and len(t) > 15)
    ):
        return True
    u = extract_urls_from_text(t, max_urls=1)
    if u and should_use_public_url_read(t):
        return False
    return should_use_web_search(t)


def should_use_public_url_read(text: str) -> bool:
    """
    True when the user likely wants a public page read (check/visit/summarize) and
    a URL is present. Excludes long prose that only mentions a link in passing.
    """
    t = (text or "").strip()
    if not extract_urls_from_text(t, max_urls=1):
        return False
    if _BARE_URL_ONLY.match(t):
        return True
    return bool(
        re.search(
            r'(?i)\b(check|visit|read|see|look (?:at|in)|open|show|load|go to|'
            r"summarize|pull up|scrape|what(?:'s| is| are)|which|"
            r"any (thing|info|word)|tell me( what)?|review|compare|"
            r"products?|services?|offerings?|"
            r"on (this |the |that )?(site|page|url|web|domain|website)\b|"
            r"check (?:this|that|the) site|"
            r"does .+ (have|offer|list)|what .+ (sell|offer|have|list))",
            t,
        )
    )
