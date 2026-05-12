# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Rewrite legacy identity leaks in user-visible gateway output (Phase 51)."""

from __future__ import annotations

import re

from app.services.identity.legacy_strings import legacy_identity_violations, scrub_allowed_api_paths

_RE_TELL_CURSOR_TO = re.compile(r"tell\s+Cursor\s+to\s*", re.IGNORECASE)
_RE_TELL_CURSOR = re.compile(r"tell\s+Cursor\b", re.IGNORECASE)
_RE_REST_METHOD_PATH = re.compile(
    r"\b(?:POST|GET|PUT|PATCH|DELETE)\s+/api/v[^\s`]+",
    re.IGNORECASE,
)
_RE_BACKTICK_API = re.compile(r"`/api/v[^`]+`")


def gateway_identity_needs_scrub(text: str) -> bool:
    """True if outgoing copy should be normalized (legacy markers or REST-in-chat hints)."""
    if legacy_identity_violations(text):
        return True
    t = scrub_allowed_api_paths(text or "")
    low = t.lower()
    if "tell cursor" in low:
        return True
    if "development agent" in low:
        return True
    if _RE_REST_METHOD_PATH.search(t):
        return True
    if "/api/v1/dev/" in low:
        return True
    return False


def scrub_legacy_identity_text(text: str) -> str:
    """Best-effort replacement so Nexa reads as one system, not a compatibility layer."""
    t = scrub_allowed_api_paths(text or "")
    t = _RE_TELL_CURSOR_TO.sub("I can ", t)
    t = _RE_TELL_CURSOR.sub("I can run this", t)
    t = t.replace("Development agent", "Nexa")
    t = t.replace("development agent", "Nexa")
    t = t.replace("Dev Agent", "Nexa")
    t = t.replace("Development Agent", "Nexa")
    t = _RE_REST_METHOD_PATH.sub("Mission Control (Dev workspace)", t)
    t = _RE_BACKTICK_API.sub("Mission Control", t)
    t = re.sub(
        r"\bPOST\s+/api/v1/dev/(?:workspaces|runs)\b[^.!?]*",
        "Add or pick a workspace in Mission Control, then say run dev: … with your goal.",
        t,
        flags=re.IGNORECASE,
    )
    # Slash-invocations often leaked from old UX
    for sym in ("@dev", "@ops", "@research", "@strategy"):
        t = t.replace(sym, "")
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


__all__ = ["gateway_identity_needs_scrub", "scrub_legacy_identity_text"]
