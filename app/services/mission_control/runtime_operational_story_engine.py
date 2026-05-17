# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Coherent runtime operational narratives (Phase 4 Step 23)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_assurance_engine import build_runtime_assurance_engine
from app.services.mission_control.runtime_operational_state_machine import build_runtime_operational_state_machine


def build_runtime_operational_story_engine(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    state = build_runtime_operational_state_machine(truth)["runtime_operational_state"]["state"]
    assurance = build_runtime_assurance_engine(truth)["runtime_assurance"]
    stories: list[str] = []
    if state == "recovering":
        stories.append("AethOS completed startup recovery and restored enterprise runtime coordination.")
    if (truth.get("hydration_progress") or {}).get("partial"):
        stories.append("AethOS resumed enterprise intelligence after recovering hydration state.")
    if (truth.get("routing_summary") or {}).get("fallback_used"):
        stories.append("Routing stability improved after provider recovery.")
    if (truth.get("runtime_stability") or {}).get("stable"):
        stories.append("AethOS runtime stability remained consistent during extended operation.")
    if not stories:
        stories.append(assurance.get("summary") or "AethOS runtime is operating with enterprise coordination.")
    journey = stories[-5:]
    headline = journey[-1] if journey else ""
    return {
        "runtime_operational_story": {"headline": headline, "stories": journey, "bounded": True},
        "enterprise_runtime_narrative": {"narrative": headline, "bounded": True},
        "runtime_operational_journey": {"steps": journey, "bounded": True},
        "enterprise_operational_story_final": {
            "unified": True,
            "domains": ["startup", "recovery", "readiness", "degraded", "continuity", "routing", "hydration", "trust"],
            "headline": headline,
            "bounded": True,
        },
        "runtime_operational_timeline_story": {"events": journey, "bounded": True},
        "runtime_enterprise_posture_story": {
            "posture": (truth.get("runtime_production_certification") or {}).get("production_grade"),
            "narrative": headline,
            "bounded": True,
        },
        "phase": "phase4_step24",
        "bounded": True,
    }


def build_runtime_operational_story_final(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    engine = build_runtime_operational_story_engine(truth)
    return {
        "runtime_operational_story_final": engine.get("enterprise_operational_story_final") or {},
        "enterprise_operational_story_final": engine.get("enterprise_operational_story_final") or {},
        "runtime_operational_timeline_story": engine.get("runtime_operational_timeline_story") or {},
        "runtime_enterprise_posture_story": engine.get("runtime_enterprise_posture_story") or {},
        "phase": "phase4_step24",
        "bounded": True,
    }
