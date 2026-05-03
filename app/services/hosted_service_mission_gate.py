"""
Block generic mission parsing for hosted infra / deploy-shaped asks (P0 trust).

Railway URL + prose lines must not produce loose missions with agent role ``https``.
"""

from __future__ import annotations

import re

from app.services.intent_classifier import looks_like_external_execution, looks_like_external_investigation

# Known hosted dashboards / deploy surfaces (substring match).
_PROVIDER_HOST_RE = re.compile(
    r"(?i)(railway\.com|railway\.app|render\.com|fly\.io|vercel\.app|netlify\.app|herokuapp\.com)",
)

_ANY_HTTP = re.compile(r"https?://\S+")

# Signals “external ops” when combined with investigation intent or URLs.
_OPS_TERMS = re.compile(
    r"(?i)\b(railway|render\.com|fly\.io|flyctl|heroku|vercel|netlify|cloudflare|"
    r"aws\b|gcp|azure|kubernetes|kubectl|terraform|deploy|redeploy|production|"
    r"service crashed|service failing|hosted)\b",
)


def hosted_service_mission_blocked(text: str) -> bool:
    """
    True → ``parse_mission`` must return None; gateway should fall through to chat routing.

    Conservative: hosted-service asks use external_execution / investigation paths, not generic missions.
    """
    t = (text or "").strip()
    if not t:
        return False

    if looks_like_external_execution(t):
        return True

    if looks_like_external_investigation(t):
        if _PROVIDER_HOST_RE.search(t) or _ANY_HTTP.search(t):
            return True
        if _OPS_TERMS.search(t):
            return True

    if _PROVIDER_HOST_RE.search(t):
        return True

    if _ANY_HTTP.search(t) and _OPS_TERMS.search(t):
        return True

    return False


__all__ = ["hosted_service_mission_blocked"]
