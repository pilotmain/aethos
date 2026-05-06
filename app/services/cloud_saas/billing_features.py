"""Feature matrix and limits by subscription tier (cloud billing)."""

from __future__ import annotations


def get_features_for_tier(tier: str) -> dict[str, object]:
    t = (tier or "free").strip().lower()
    features = {
        "free": {
            "agents": 1,
            "tokens_per_month": 10000,
            "history_days": 7,
            "support": "community",
            "rbac": False,
            "audit_logs": False,
        },
        "pro": {
            "agents": 5,
            "tokens_per_month": 100000,
            "history_days": 30,
            "support": "email",
            "rbac": False,
            "audit_logs": False,
        },
        "business": {
            "agents": 25,
            "tokens_per_month": 1000000,
            "history_days": 90,
            "support": "priority",
            "rbac": True,
            "audit_logs": True,
        },
        "enterprise": {
            "agents": -1,
            "tokens_per_month": -1,
            "history_days": 365,
            "support": "dedicated",
            "rbac": True,
            "audit_logs": True,
        },
    }
    return features.get(t, features["free"])


TIER_ORDER = {"free": 0, "pro": 1, "business": 2, "enterprise": 3}


def tier_at_least(org_tier: str, min_tier: str) -> bool:
    a = TIER_ORDER.get((org_tier or "free").strip().lower(), 0)
    b = TIER_ORDER.get((min_tier or "free").strip().lower(), 0)
    return a >= b


__all__ = ["get_features_for_tier", "TIER_ORDER", "tier_at_least"]
