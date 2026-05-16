# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Advanced brain / provider routing visibility (Phase 3 Step 1)."""

from __future__ import annotations

from typing import Any

from app.brain.brain_events import recent_brain_decisions
from app.core.config import get_settings
from app.privacy.privacy_policy import current_privacy_mode
def build_brain_routing_panel() -> dict[str, Any]:
    from app.services.mission_control.runtime_truth import build_provider_routing_summary

    summary = build_provider_routing_summary()
    recent = recent_brain_decisions(limit=5)
    s = get_settings()
    mode = current_privacy_mode(s)
    chain: list[str] = []
    if summary.get("provider"):
        chain.append(str(summary["provider"]))
    for row in recent[1:3]:
        p = row.get("selected_provider")
        if p and p not in chain:
            chain.append(str(p))
    fallback = chain[1] if len(chain) > 1 else None
    return {
        "brain_routing": {
            "selected_provider": summary.get("provider"),
            "fallback_provider": fallback,
            "selected_model": summary.get("model"),
            "reason": summary.get("reason"),
            "privacy_mode": mode.value,
            "local_first": summary.get("local_first"),
            "local_only": summary.get("local_only"),
            "fallback_used": summary.get("fallback_used"),
            "provider_preference_chain": chain,
            "estimated_cost": _estimate_cost(recent[0] if recent else {}),
            "provider_health": "ok" if not summary.get("privacy_block_active") else "restricted",
        },
        "recent_decisions": recent,
    }


def _estimate_cost(decision: dict[str, Any]) -> float | None:
    tokens = decision.get("estimated_tokens") or decision.get("tokens")
    if isinstance(tokens, (int, float)) and tokens > 0:
        return round(float(tokens) * 0.000002, 4)
    return None
