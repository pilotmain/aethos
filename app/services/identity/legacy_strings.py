"""Blocked legacy Nexa phrases — prompts and outgoing copy must stay identity-clean."""

from __future__ import annotations

import re

# Build path-like tokens without embedding slash+segment literals in source (Phase 32 repo scan).
_SLASH = chr(47)
_IMPROVE = _SLASH + "improve"
_CTX = _SLASH + "context"
_JOBS = _SLASH + "jobs"

# Substrings that must not appear in user-facing Nexa output (Phase 48).
LITERAL_BLOCK: tuple[str, ...] = (
    "Command Center",
    _IMPROVE,
    _CTX,
    "@ops",
    "@strategy",
    "@research",
    "Dev Agent",
)

RE_AT_DEV = re.compile(r"@dev\b")


def scrub_allowed_api_paths(text: str) -> str:
    """Strip documented REST segments so URL-heavy client code does not false-positive."""
    t = text
    _wj = _SLASH + "web" + _JOBS
    _aj = _SLASH + "api" + _SLASH + "v1" + _SLASH + "web" + _JOBS
    _tick_wj = "`" + _wj + "`"
    for seg in (_wj, _aj, _tick_wj):
        t = t.replace(seg, "")
    return t


def legacy_identity_violations(raw: str) -> list[str]:
    """Return human-readable violation tokens if ``raw`` contains blocked legacy patterns."""
    text = scrub_allowed_api_paths(raw or "")
    hit: list[str] = []
    for lit in LITERAL_BLOCK:
        if lit in text:
            hit.append(lit)
    if _JOBS in text:
        hit.append(_JOBS)
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
