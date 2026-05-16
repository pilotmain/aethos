# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Worker ecosystem experience layer (Phase 4 Step 9)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.mission_control_language_system import translate_term
from app.services.mission_control.worker_operational_lifecycle import build_worker_operational_lifecycle


def build_worker_specialization_narratives(truth: dict[str, Any] | None = None) -> list[str]:
    truth = truth or {}
    smap = truth.get("worker_specialization_map") or {}
    if not isinstance(smap, dict) or not smap:
        return ["Workers specialize on demand under orchestrator assignment."]
    roles = list(smap.keys())[:6]
    return [f"Specialization active: {', '.join(str(r) for r in roles)}."]


def build_lifecycle_storytelling(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    lifecycle = build_worker_operational_lifecycle(truth)
    maturity = lifecycle.get("worker_lifecycle_maturity") or {}
    stages = maturity.get("stages") or []
    return {
        "journey": " → ".join(stages[:7]) if stages else "spawned → active → trusted",
        "maturity_level": maturity.get("maturity_level"),
        "active_workers": maturity.get("active_workers"),
        "orchestrator_led": True,
    }


def build_worker_collaboration_story(truth: dict[str, Any] | None = None) -> str:
    truth = truth or {}
    coord = truth.get("worker_coordination_quality") or {}
    quality = coord.get("score") if isinstance(coord, dict) else None
    active = (truth.get("runtime_workers") or {}).get("active_count")
    if quality is not None:
        return f"Orchestrator coordinates {active or 0} workers — collaboration quality {quality}."
    return f"Orchestrator-led worker ecosystem — {active or 0} active runtime specialists."


def build_worker_contribution_highlights(truth: dict[str, Any] | None = None) -> list[str]:
    truth = truth or {}
    highlights: list[str] = []
    eco = truth.get("worker_ecosystem_health") or {}
    if isinstance(eco, dict) and eco.get("status"):
        highlights.append(f"Ecosystem health: {eco.get('status')}.")
    trust = (truth.get("worker_trust_model") or {}).get("trust_indicator")
    if trust:
        highlights.append(f"Trust indicator: {trust}.")
    highlights.append(translate_term("continuity") + " via deliverables and archival lineage.")
    return highlights[:8]


def build_worker_ecosystem_experience(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    lifecycle = build_lifecycle_storytelling(truth)
    return {
        "worker_ecosystem_experience": {
            "headline": "Worker ecosystem — orchestrator-led specialists",
            "collaboration_visible": True,
            "bounded": True,
            "enterprise_readable": True,
        },
        "worker_contribution_highlights": build_worker_contribution_highlights(truth),
        "worker_collaboration_story": build_worker_collaboration_story(truth),
        "worker_specialization_narratives": build_worker_specialization_narratives(truth),
        "lifecycle_storytelling": lifecycle,
        "worker_trust_explanation": (build_worker_operational_lifecycle(truth).get("worker_specialization_trust") or {}),
    }
