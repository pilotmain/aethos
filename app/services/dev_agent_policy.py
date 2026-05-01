"""Static policy gate for dev job instructions (no user-controlled shell)."""
from __future__ import annotations

BLOCKED_TERMS = [
    ".env",
    "ssh",
    "id_rsa",
    "private key",
    "password",
    "token",
    "credential",
    "delete everything",
    "rm -rf",
    "drop database",
    "push to main",
    "merge to main",
]

HIGH_RISK_TERMS = [
    "auth",
    "payment",
    "billing",
    "security",
    "database migration",
    "production",
    "deploy",
]


def evaluate_dev_job_policy(text: str) -> dict:
    t = (text or "").lower()

    blocked_hits = [term for term in BLOCKED_TERMS if term in t]
    high_risk_hits = [term for term in HIGH_RISK_TERMS if term in t]

    if blocked_hits:
        return {
            "allowed": False,
            "risk": "blocked",
            "reason": f"Blocked terms: {', '.join(blocked_hits)}",
            "requires_extra_approval": False,
        }

    if high_risk_hits:
        return {
            "allowed": True,
            "risk": "high",
            "reason": f"High-risk terms: {', '.join(high_risk_hits)}",
            "requires_extra_approval": True,
        }

    return {
        "allowed": True,
        "risk": "normal",
        "reason": "Allowed",
        "requires_extra_approval": False,
    }
