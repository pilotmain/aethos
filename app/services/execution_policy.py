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


__all__ = ["assess_interaction_risk", "should_auto_execute"]
