"""
Early provider intent routing (Vercel / Railway / GitHub / generic).

Used before operator runner selection and before Railway-only external execution
so Vercel URLs and vercel.com visits do not fall through to Railway defaults.
"""

from __future__ import annotations

import logging
import re
logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://[^\s)>`\"']+", re.I)

# Below this, callers may treat intent as ambiguous (no strong default).
CONFIDENCE_SOFT_GATE = 0.6


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
    text_lower = (intent_text or "").lower()
    url_str = " ".join(urls).lower()

    vercel_score = 0.0
    if "vercel.com" in url_str or ".vercel.app" in url_str or "vercel.app" in url_str:
        vercel_score = max(vercel_score, 0.95)
    if "vercel.com" in text_lower or "vercel.app" in text_lower:
        vercel_score = max(vercel_score, 0.92)
    if re.search(r"\bvercel\b", text_lower):
        vercel_score = max(vercel_score, 0.88)
    if "vercel deploy" in text_lower or "vercel production" in text_lower:
        vercel_score = max(vercel_score, 1.0)

    railway_score = 0.0
    if "railway.app" in url_str or "railway.com" in url_str:
        railway_score = max(railway_score, 0.92)
    if re.search(r"\brailway\b", text_lower):
        railway_score = max(railway_score, 0.9)

    github_score = 0.0
    if "github.com" in url_str or "git@" in url_str:
        github_score = max(github_score, 0.9)
    if re.search(r"\bgithub\b", text_lower) or re.search(r"\bgh\s+", text_lower):
        github_score = max(github_score, 0.85)
    if "push to remote" in text_lower:
        github_score = max(github_score, 0.82)

    scores = {
        "vercel": vercel_score,
        "railway": railway_score,
        "github": github_score,
        "generic": 0.3,
    }
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
    hosts = {k: v for k, v in scores.items() if k != "generic"}
    ranked_hosts = sorted(hosts.items(), key=lambda kv: kv[1], reverse=True)
    if len(ranked_hosts) >= 2:
        (_n1, s1), (_n2, s2) = ranked_hosts[0], ranked_hosts[1]
        if s1 - s2 < tie_margin and s2 >= 0.55:
            return "generic", min(0.55, max(0.35, s2 - 0.4))
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_name, best = ranked[0]
    return best_name, float(best)


def apply_router_to_operator_hints(text: str, hints: dict[str, bool]) -> dict[str, bool]:
    """
    Overlay :func:`detect_primary_provider` on :func:`detect_provider_hints` output.

    When Vercel clearly dominates Railway, clears ``railway`` so the operator loop
    does not defer to the execution-loop Railway path for the same turn.
    """
    urls = extract_urls_from_text(text)
    scores = _score_signals(text, urls)
    prov, conf = detect_primary_provider(text, urls)
    out = dict(hints)
    logger.info(
        "provider_router.operator_scores vercel=%.2f railway=%.2f github=%.2f picked=%s conf=%.2f",
        scores["vercel"],
        scores["railway"],
        scores["github"],
        prov,
        conf,
    )
    if prov == "vercel" and scores["vercel"] >= scores["railway"] + 0.04:
        out["vercel"] = True
        out["railway"] = False
    elif prov == "railway" and scores["railway"] >= scores["vercel"] + 0.04:
        out["railway"] = True
        out["vercel"] = False
    elif prov == "github" and conf >= CONFIDENCE_SOFT_GATE:
        out["github"] = True
    return out


def should_skip_railway_bounded_path(user_text: str) -> bool:
    """
    True when this message is dominated by Vercel (or ambiguous tie), not Railway.

    Used to avoid running ``run_bounded_railway_repo_investigation`` for obvious
    Vercel-only intents (e.g. ``vercel.com`` + deployment URL).
    """
    raw = (user_text or "").strip()
    if not raw:
        return False
    tl = raw.lower()
    urls = extract_urls_from_text(raw)
    scores = _score_signals(raw, urls)
    if re.search(r"\brailway\b", tl) and scores["railway"] >= 0.88:
        return False
    if re.search(r"\brailway\b", tl) and "vercel" not in tl:
        if "railway.app" in tl or "railway.com" in tl:
            return False
    prov, conf = detect_primary_provider(raw, urls)
    if prov == "generic" and conf < CONFIDENCE_SOFT_GATE and scores["vercel"] < 0.5 and scores["railway"] < 0.5:
        return False
    if prov == "vercel" and scores["vercel"] >= scores["railway"] + 0.04:
        return True
    if prov == "generic" and scores["vercel"] > 0.5 and scores["vercel"] >= scores["railway"]:
        return True
    return False


def format_provider_clarification_blocker() -> str:
    return (
        "### Provider routing\n\n"
        "I could not confidently tell whether you mean **Vercel**, **Railway**, **GitHub**, or another host "
        f"(signals were below {CONFIDENCE_SOFT_GATE:.0%} or tied).\n\n"
        "Reply with one line naming the provider and paste the relevant URL (e.g. `vercel.com` deployment or "
        "`railway.app` project)."
    )


__all__ = [
    "CONFIDENCE_SOFT_GATE",
    "apply_router_to_operator_hints",
    "detect_primary_provider",
    "extract_urls_from_text",
    "format_provider_clarification_blocker",
    "should_skip_railway_bounded_path",
]
