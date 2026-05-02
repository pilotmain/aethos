"""Blocked legacy Nexa phrases — prompts and outgoing copy must stay identity-clean."""

from __future__ import annotations

import re

# Substrings that must not appear in user-facing Nexa output (Phase 48).
LITERAL_BLOCK: tuple[str, ...] = (
    "Command Center",
    "/improve",
    "/context",
    "@ops",
    "@strategy",
    "@research",
    "Dev Agent",
)

RE_AT_DEV = re.compile(r"@dev\b")


def scrub_allowed_api_paths(text: str) -> str:
    """Strip documented REST segments so URL-heavy client code does not false-positive."""
    t = text
    for seg in ("/web/jobs", "/api/v1/web/jobs", "`/web/jobs`"):
        t = t.replace(seg, "")
    return t


def legacy_identity_violations(raw: str) -> list[str]:
    """Return human-readable violation tokens if ``raw`` contains blocked legacy patterns."""
    text = scrub_allowed_api_paths(raw or "")
    hit: list[str] = []
    for lit in LITERAL_BLOCK:
        if lit in text:
            hit.append(lit)
    if "/jobs" in text:
        hit.append("/jobs")
    if RE_AT_DEV.search(text):
        hit.append("@dev")
    return sorted(set(hit))


def no_legacy_identity_strings(text: str) -> bool:
    """True iff ``text`` has no blocked legacy identity markers."""
    return not legacy_identity_violations(text)


__all__ = [
    "LITERAL_BLOCK",
    "legacy_identity_violations",
    "no_legacy_identity_strings",
    "scrub_allowed_api_paths",
]
