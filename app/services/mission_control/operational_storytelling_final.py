# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operational storytelling — launch completion (Phase 4 Step 13)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.operational_narrative_engine import build_operational_narratives_v2
from app.services.mission_control.runtime_recovery_experience import build_runtime_recovery_experience


def build_operational_storytelling_final(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    v2 = build_operational_narratives_v2(truth)
    recovery = build_runtime_recovery_experience(truth)
    return {
        "operational_storytelling_final": {
            "headline": _headline(truth),
            "what_is_happening": v2.get("operational_narratives_v2", {}).get("recovery_summary"),
            "why_it_matters": "Orchestrator maintains visibility, accountability, and calm operations.",
            "what_changed": (v2.get("operational_narratives_v2") or {}).get("shifts", [])[:4],
            "what_is_healthy": (truth.get("operational_summary") or {}).get("health"),
            "what_is_recovering": recovery.get("runtime_recovery_experience", {}).get("headline"),
            "what_needs_attention": _needs_attention(truth),
            "what_aethos_is_doing": "Coordinating workers, routing providers, and governing operations.",
            "bounded": True,
        },
        "runtime_storyline": v2.get("runtime_storyline"),
    }


def _headline(truth: dict[str, Any]) -> str:
    health = (truth.get("operational_summary") or {}).get("health") or "nominal"
    return f"AethOS operational story — {health} posture under orchestrator authority."


def _needs_attention(truth: dict[str, Any]) -> list[str]:
    items: list[str] = []
    esc = int((truth.get("runtime_escalations") or {}).get("escalation_count") or 0)
    if esc:
        items.append(f"{esc} escalation(s) visible on governance timeline")
    if (truth.get("routing_summary") or {}).get("fallback_used"):
        items.append("AethOS routed through an alternate provider — review routing explanations")
    return items[:6]
