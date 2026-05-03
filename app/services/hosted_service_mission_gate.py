"""
Block generic mission parsing for hosted infra / deploy-shaped asks (P0 trust).

Hosted dashboard URLs must not spawn Agent Graph tasks (including fake ``@https`` agents).
Railway/deploy surfaces route through ``external_execution`` / ``external_execution_runner``, not ``parse_mission``.
"""

from __future__ import annotations

import re

from app.services.intent_classifier import looks_like_external_execution, looks_like_external_investigation

# Known hosted dashboards / deploy surfaces (substring match).
_PROVIDER_HOST_RE = re.compile(
    r"(?i)(railway\.com|railway\.app|render\.com|fly\.io|vercel\.app|netlify\.app|herokuapp\.com)",
)

_ANY_HTTP = re.compile(r"https?://\S+")

# Lines pasted from URLs accidentally parsed as ``@https: //host/...`` mission tasks.
_RE_SCHEME_AGENT_LINE = re.compile(r"(?im)^\s*@(https?)\s*:")

# Signals “external ops” when combined with investigation intent or URLs.
_OPS_TERMS = re.compile(
    r"(?i)\b(railway|render\.com|fly\.io|flyctl|heroku|vercel|netlify|cloudflare|"
    r"aws\b|gcp|azure|kubernetes|kubectl|terraform|deploy|redeploy|production|"
    r"service crashed|service failing|hosted)\b",
)


def hosted_deploy_provider_match(text: str) -> bool:
    """True when text references a known PaaS/deploy dashboard host (Railway, Render, …)."""
    return bool(_PROVIDER_HOST_RE.search(text or ""))


def hosted_service_mission_blocked(text: str) -> bool:
    """
    True → ``parse_mission`` must return None; gateway should fall through to chat routing.

    Conservative: hosted-service asks use external_execution / investigation paths, not generic missions.
    """
    t = (text or "").strip()
    if not t:
        return False

    if _RE_SCHEME_AGENT_LINE.search(t):
        return True

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


__all__ = ["hosted_deploy_provider_match", "hosted_service_mission_blocked"]
