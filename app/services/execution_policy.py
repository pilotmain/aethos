# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 50 — when Nexa should take action-first paths vs pause for confirmation."""

from __future__ import annotations

import re

# Destructive / production-touching language raises risk tier before auto-assist.
_HIGH_RISK = re.compile(
    r"(?i)\b("
    r"rm\s+-rf|drop\s+database|truncate\s+table|delete\s+from\b.*\bwhere\b.*\b1\s*=\s*1|"
    r"production\b.*\b(deploy|migrate|exec)|\bprod\b.*\bmigrate|"
    r"force\s+push|--no-verify|--no-gpg-sign.*push|chmod\s+777|"
    r"cascade\s+delete|disable\s+2fa|rotate\s+all\s+keys"
    r")\b"
)

_MEDIUM_RISK = re.compile(
    r"(?i)\b(migrate\b.*\b(db|database)|helm\s+upgrade|kubectl\s+apply|"
    r"terraform\s+apply|docker\s+push.*prod|cut\s+over|blue.?green)\b"
)


def assess_interaction_risk(user_text: str) -> str:
    """Coarse risk tier from message text (no execution — pattern-only)."""
    t = (user_text or "").strip()
    if not t:
        return "low"
    if _HIGH_RISK.search(t):
        return "high"
    if _MEDIUM_RISK.search(t):
        return "medium"
    return "low"


def should_auto_execute(intent: str, risk: str) -> bool:
    """True when policy favors immediate action-first handling (safe contexts only)."""
    if risk != "low":
        return False
    return intent in ("stuck_dev", "analysis")


def contains_destructive_language(text: str) -> bool:
    """High-risk phrases — do not auto-run dev missions."""
    return assess_interaction_risk(text) == "high"


def user_said_do_not_run(text: str) -> bool:
    """True when the user explicitly opted out of automated execution."""
    tl = (text or "").lower()
    for phrase in (
        "don't run",
        "do not run",
        "dont run",
        "don't execute",
        "do not execute",
        "just explain",
        "only explain",
        "no execution",
        "don't change code",
        "do not change",
        "theory only",
        "do not run anything",
        "don't run anything",
    ):
        if phrase in tl:
            return True
    return False


def should_auto_run_dev_task(
    intent: str,
    risk: str,
    workspace_count: int,
    text: str,
) -> bool:
    """
    Phase 52 — safe low-risk auto dev investigation when exactly one workspace exists.

    Requires explicit ``run dev`` elsewhere; this gates *automatic* investigation runs only.
    """
    if workspace_count != 1:
        return False
    if intent not in ("stuck_dev", "analysis"):
        return False
    if risk != "low":
        return False
    if contains_destructive_language(text):
        return False
    if user_said_do_not_run(text):
        return False
    return True


def should_auto_execute_dev_turn(
    intent: str,
    risk: str,
    workspace_count: int,
    text: str,
) -> bool:
    """Phase 53 alias — same rules as :func:`should_auto_run_dev_task`."""
    return should_auto_run_dev_task(intent, risk, workspace_count, text)


def should_prompt_for_dev_workspace_help(intent: str, risk: str, text: str) -> bool:
    """
    When auto-run is impossible (0 or multiple workspaces), still offer UX guidance for
    low-risk stuck-dev-style turns — without executing anything.
    """
    if intent not in ("stuck_dev", "analysis"):
        return False
    if risk != "low":
        return False
    if contains_destructive_language(text):
        return False
    if user_said_do_not_run(text):
        return False
    return True


__all__ = [
    "assess_interaction_risk",
    "contains_destructive_language",
    "should_auto_execute",
    "should_auto_run_dev_task",
    "should_auto_execute_dev_turn",
    "should_prompt_for_dev_workspace_help",
    "user_said_do_not_run",
]
