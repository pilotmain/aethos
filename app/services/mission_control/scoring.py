"""Deterministic priority scoring for Mission Control (V1 — no AI)."""

from __future__ import annotations

from typing import Any

_TYPE_SCORE: dict[str, int] = {
    "pending_approval": 100,
    "blocked_high_risk": 90,
    "gateway_outbound_failed": 85,
    "failed_job": 80,
    "sensitive_warning": 70,
    "running_job": 40,
    "recent_allowed": 10,
    "recommendation": 5,
    "active_job": 35,
}


def score_mission_item(item: dict[str, Any]) -> int:
    """Return priority score for sorting the attention queue (higher = more urgent)."""
    t = str(item.get("type") or "").strip().lower()
    return _TYPE_SCORE.get(t, 0)
