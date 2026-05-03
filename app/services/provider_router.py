"""
Early provider intent routing from URLs + keywords (extensible tables).

Used before operator runner selection and before Railway-only external execution
so Vercel URLs and other hosts do not fall through to Railway defaults.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://[^\s)>`\"']+", re.I)

# Below this, callers may treat intent as ambiguous (no strong default).
CONFIDENCE_SOFT_GATE = 0.6

# (URL substring must appear in joined lowercased URLs), provider, weight
_URL_RULES: tuple[tuple[tuple[str, ...], str, float], ...] = (
    (("vercel.com", ".vercel.app", "vercel.app"), "vercel", 1.0),
    (("railway.app", "railway.com"), "railway", 1.0),
    (("github.com", "git@github.com:", "git@"), "github", 0.95),
    (("aws.amazon.com", ".amazonaws.com", ".aws."), "aws", 0.95),
    (("cloud.google.com", "googleapis.com", ".run.app"), "gcp", 0.92),
    (("azure.com", ".azurewebsites.net", "portal.azure.com"), "azure", 0.92),
    ((".fly.dev", "fly.io"), "fly", 1.0),
    (("onrender.com", "render.com"), "render", 1.0),
    (("netlify.app", "netlify.com"), "netlify", 1.0),
    (("digitalocean.com", "ondigitalocean.app"), "digitalocean", 0.95),
)

# (pattern, provider, weight) — pattern is str (substring in lower text) or compiled regex
_KW_RULES: tuple[tuple[Any, str, float], ...] = (
    (re.compile(r"\bvercel\b"), "vercel", 0.9),
    ("vercel deploy", "vercel", 1.0),
    ("vercel production", "vercel", 1.0),
    (re.compile(r"\brailway\b"), "railway", 0.9),
    (re.compile(r"\bgithub\b"), "github", 0.85),
    (re.compile(r"\bgh\s+"), "github", 0.85),
    ("push to remote", "github", 0.85),
    ("push change", "github", 0.85),
    (re.compile(r"\baws\b"), "aws", 0.85),
    (re.compile(r"\bamazon\b"), "aws", 0.85),
    (re.compile(r"\bgcp\b"), "gcp", 0.85),
    ("google cloud", "gcp", 0.82),
    (re.compile(r"\bazure\b"), "azure", 0.85),
    (re.compile(r"\bfly\.io\b"), "fly", 0.9),
    (re.compile(r"\brender\b"), "render", 0.88),
    (re.compile(r"\bnetlify\b"), "netlify", 0.88),
    (re.compile(r"\bdigitalocean\b"), "digitalocean", 0.88),
)

# Non-Railway hosts that should win bounded Railway investigation skips when dominant.
_NON_RAILWAY_DOMINANT: frozenset[str] = frozenset(
    {
        "vercel",
        "github",
        "aws",
        "fly",
        "render",
        "netlify",
        "gcp",
        "azure",
        "digitalocean",
    }
)


def extract_urls_from_text(text: str) -> list[str]:
    """Return http(s) URLs found in user text (deduped, order preserved)."""
    raw = text or ""
    seen: set[str] = set()
    out: list[str] = []
    for m in _URL_RE.findall(raw):
        u = m.rstrip(").,;]")
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _score_signals(intent_text: str, urls: list[str]) -> dict[str, float]:
    """Neutral generic floor + table-driven URL and keyword boosts (no Railway-first bias)."""
    text_lower = (intent_text or "").lower()
    url_str = " ".join(urls).lower()

    scores: dict[str, float] = {"generic": 0.2}

    for patterns, prov, w in _URL_RULES:
        if any(p in url_str for p in patterns):
            scores[prov] = max(scores.get(prov, 0.0), w)

    for pattern, prov, w in _KW_RULES:
        if isinstance(pattern, re.Pattern):
            hit = bool(pattern.search(text_lower))
        else:
            hit = str(pattern).lower() in text_lower
        if hit:
            scores[prov] = max(scores.get(prov, 0.0), w)

    return scores


def detect_primary_provider(intent_text: str, urls: list[str] | None = None) -> tuple[str, float]:
    """
    Return ``(provider, confidence)`` using URL + keyword signals.

    On a near-tie between two non-generic hosts (scores within ``tie_margin``),
    returns ``("generic", low_conf)`` so callers can ask for clarification instead
    of picking the wrong default.
    """
    u = urls if urls is not None else extract_urls_from_text(intent_text)
    scores = _score_signals(intent_text, u)
    tie_margin = 0.09
    hosts = {k: v for k, v in scores.items() if k != "generic" and v > 0}
    ranked_hosts = sorted(hosts.items(), key=lambda kv: kv[1], reverse=True)
    if len(ranked_hosts) >= 2:
        (_n1, s1), (_n2, s2) = ranked_hosts[0], ranked_hosts[1]
        if s1 - s2 < tie_margin and s2 >= 0.55:
            return "generic", min(0.55, max(0.35, s2 - 0.4))
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_name, best = ranked[0]
    logger.info(
        "provider_router.dynamic_detected provider=%s confidence=%.2f",
        best_name,
        float(best),
    )
    return best_name, float(best)


def apply_router_to_operator_hints(text: str, hints: dict[str, bool]) -> dict[str, bool]:
    """
    Overlay :func:`detect_primary_provider` on :func:`detect_provider_hints` output.

    When a non-Railway host clearly dominates Railway, clears ``railway`` so the operator loop
    does not defer to the execution-loop Railway path for the same turn.
    """
    urls = extract_urls_from_text(text)
    scores = _score_signals(text, urls)
    prov, conf = detect_primary_provider(text, urls)
    out = dict(hints)
    score_summary = " ".join(f"{k}={scores[k]:.2f}" for k in sorted(scores) if scores[k] > 0)
    logger.info(
        "provider_router.operator_scores %s picked=%s conf=%.2f",
        score_summary,
        prov,
        conf,
    )

    r_s = scores.get("railway", 0.0)
    v_s = scores.get("vercel", 0.0)

    if prov == "vercel" and v_s >= r_s + 0.04:
        out["vercel"] = True
        out["railway"] = False
    elif prov == "railway" and r_s >= v_s + 0.04:
        out["railway"] = True
        out["vercel"] = False
    elif prov in _NON_RAILWAY_DOMINANT and conf >= CONFIDENCE_SOFT_GATE:
        if prov in out:
            out[prov] = True
        if r_s > 0 and scores.get(prov, 0.0) >= r_s + 0.04:
            out["railway"] = False
    return out


def should_skip_railway_bounded_path(user_text: str) -> bool:
    """
    True when this message is dominated by a non-Railway host (or ambiguous tie), not Railway.

    Used to avoid running ``run_bounded_railway_repo_investigation`` for obvious
    non-Railway intents (e.g. ``vercel.com`` + deployment URL).
    """
    raw = (user_text or "").strip()
    if not raw:
        return False
    tl = raw.lower()
    urls = extract_urls_from_text(raw)
    scores = _score_signals(raw, urls)
    r_s = scores.get("railway", 0.0)
    if re.search(r"\brailway\b", tl) and r_s >= 0.88:
        return False
    if re.search(r"\brailway\b", tl) and "vercel" not in tl:
        if "railway.app" in tl or "railway.com" in tl:
            return False
    prov, conf = detect_primary_provider(raw, urls)
    v_s = scores.get("vercel", 0.0)
    if prov == "generic" and conf < CONFIDENCE_SOFT_GATE and v_s < 0.5 and r_s < 0.5:
        return False
    if prov == "vercel" and v_s >= r_s + 0.04:
        return True
    if prov in _NON_RAILWAY_DOMINANT and prov != "vercel" and scores.get(prov, 0.0) >= r_s + 0.04:
        return True
    if prov == "generic" and v_s > 0.5 and v_s >= r_s:
        return True
    return False


def format_provider_clarification_blocker() -> str:
    return (
        "### Provider routing\n\n"
        "I could not confidently tell which cloud or host you mean "
        f"(signals were below {CONFIDENCE_SOFT_GATE:.0%} or tied).\n\n"
        "Reply with one line naming the provider and paste the relevant URL "
        "(for example a `vercel.com` deployment, `railway.app` service, or `github.com` repo)."
    )


__all__ = [
    "CONFIDENCE_SOFT_GATE",
    "apply_router_to_operator_hints",
    "detect_primary_provider",
    "extract_urls_from_text",
    "format_provider_clarification_blocker",
    "should_skip_railway_bounded_path",
]
