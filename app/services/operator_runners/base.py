"""
Shared types and provider detection for end-to-end operator orchestration.

Write/deploy paths are gated elsewhere (host executor, approvals). This package
focuses on deterministic read-only diagnostics + evidence payloads.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any


class TruthState(str, Enum):
    """Coarse execution truth — only ``verified`` may drive green completed UI."""

    access_required = "access_required"
    diagnostic_only = "diagnostic_only"
    fix_prepared = "fix_prepared"
    deployed_unverified = "deployed_unverified"
    verified = "verified"
    failed = "failed"


def format_operator_progress(lines: list[str]) -> str:
    body = "\n".join(f"→ {x}" for x in lines)
    return f"### Progress\n\n{body}"


def detect_provider_hints(text: str) -> dict[str, bool]:
    """Cheap substring/classifier hints (no LLM)."""
    t = (text or "").strip().lower()
    return {
        "vercel": bool(
            re.search(r"\bvercel\b", t)
            or ".vercel.app" in t
            or "vercel.app" in t
            or "vercel.com" in t
        ),
        "railway": bool(re.search(r"\brailway\b", t) or "railway.app" in t or "railway.com" in t),
        "github": bool(re.search(r"\bgithub\b", t) or "github.com" in t or re.search(r"\bgh\s+", t)),
        "local_git": bool(re.search(r"\bgit\b", t) or "workspace:" in t or "repo" in t),
    }


def forbid_unverified_success_language(
    *,
    body: str,
    verified: bool | None = None,
    strict_verified: bool | None = None,
) -> str:
    """
    When strict proof is missing, soften definitive success words (product truth guard).

    ``strict_verified`` is preferred (deploy + HTTP verify, etc.). If omitted, ``verified``
    is used for backward compatibility.
    """
    ok = strict_verified if strict_verified is not None else verified
    if ok is None:
        ok = False
    if ok or not (body or "").strip():
        return body
    low = body.lower()
    risky = (
        "deployed successfully",
        "healthy now",
        "fixed and deployed",
        "mission complete",
        "production is healthy",
        "deployed to production",
        " successfully deployed",
    )
    risky_word = any(w in low for w in risky) or any(
        w in low for w in (" deployed", " is healthy", "was fixed", "now healthy")
    )
    if risky_word:
        return (
            body
            + "\n\n---\n\n"
            + "_Claims like “deployed”, “healthy”, or “mission complete” require proof on this stack "
            + "(e.g. deploy command success **and** a follow-up HTTP verify in the 2xx range). "
            + "This turn does not meet that bar yet — see evidence above._"
        )
    return body


def evidence_shell(
    *,
    provider: str,
    commands: list[dict[str, Any]],
    workspace_path: str | None = None,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "workspace_path": workspace_path,
        "commands": commands,
    }


__all__ = [
    "TruthState",
    "detect_provider_hints",
    "evidence_shell",
    "forbid_unverified_success_language",
    "format_operator_progress",
]
