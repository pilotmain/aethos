# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Advanced brain / provider routing visibility (Phase 3 Step 1–2)."""

from __future__ import annotations

from typing import Any

from app.brain.brain_capabilities import BRAIN_TASKS, describe_brain
from app.brain.brain_events import recent_brain_decisions
from app.brain.brain_registry import list_repair_brain_candidates
from app.core.config import get_settings
from app.privacy.privacy_policy import current_privacy_mode


def build_brain_routing_panel() -> dict[str, Any]:
    from app.services.mission_control.runtime_truth import build_provider_routing_summary

    summary = build_provider_routing_summary()
    recent = recent_brain_decisions(limit=8)
    s = get_settings()
    mode = current_privacy_mode(s)
    candidates = list_repair_brain_candidates(s)
    chain: list[str] = []
    if summary.get("provider"):
        chain.append(str(summary["provider"]))
    for row in recent[1:3]:
        p = row.get("selected_provider")
        if p and p not in chain:
            chain.append(str(p))
    latest = recent[0] if recent else {}
    fallback_chain = latest.get("fallback_chain") or chain
    fallback = fallback_chain[1] if len(fallback_chain) > 1 else None
    fallback_count = sum(1 for r in recent if r.get("fallback_used"))
    routing_conf = latest.get("capability_score")
    if routing_conf is None:
        routing_conf = 0.85 if not summary.get("fallback_used") else 0.65
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
            "provider_preference_chain": fallback_chain,
            "fallback_chain": fallback_chain,
            "estimated_cost": latest.get("cost_estimate") or _estimate_cost(recent[0] if recent else {}),
            "provider_health": "ok" if not summary.get("privacy_block_active") else "restricted",
            "capability_score": latest.get("capability_score"),
            "routing_confidence": routing_conf,
            "fallback_frequency": round(fallback_count / max(1, len(recent)), 3),
            "privacy_routing_confidence": 1.0 if mode.value == "observe" else 0.9,
            "task": latest.get("task") or summary.get("task"),
        },
        "supported_tasks": sorted(BRAIN_TASKS),
        "candidate_brains": [
            {**row, "capabilities": describe_brain(str(row.get("provider") or ""))} for row in candidates[:6]
        ],
        "recent_decisions": recent,
    }


def _estimate_cost(decision: dict[str, Any]) -> float | None:
    if decision.get("cost_estimate") is not None:
        return float(decision["cost_estimate"])
    tokens = decision.get("estimated_tokens") or decision.get("tokens")
    if isinstance(tokens, (int, float)) and tokens > 0:
        return round(float(tokens) * 0.000002, 4)
    return None
