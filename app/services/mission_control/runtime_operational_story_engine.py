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
    if not stories:
        stories.append(assurance.get("summary") or "AethOS runtime is operating with enterprise coordination.")
    journey = stories[-3:]
    return {
        "runtime_operational_story": {"headline": journey[-1] if journey else "", "stories": journey, "bounded": True},
        "enterprise_runtime_narrative": {"narrative": journey[-1] if journey else "", "bounded": True},
        "runtime_operational_journey": {"steps": journey, "bounded": True},
        "phase": "phase4_step23",
        "bounded": True,
    }
