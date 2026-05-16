# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Conversational setup experience model (Phase 4 Step 15)."""

from __future__ import annotations

from typing import Any

FLOW = [
    {"id": "welcome", "title": "Welcome", "why": "Introduce AethOS as your operational orchestrator."},
    {"id": "runtime_strategy", "title": "Runtime strategy", "why": "Choose how reasoning runs — local, cloud, or hybrid."},
    {"id": "providers", "title": "Intelligence providers", "why": "Connect brains AethOS can route to."},
    {"id": "mission_control", "title": "Mission Control", "why": "Seed API access so the console works immediately."},
    {"id": "workspace", "title": "Workspace", "why": "Where projects and automation execute."},
    {"id": "operator_onboarding", "title": "Operator relationship", "why": "Optional personalization — calm and skippable."},
    {"id": "readiness", "title": "Operational readiness", "why": "Validate runtime before you rely on it."},
    {"id": "launch", "title": "Launch", "why": "Open Mission Control with confidence."},
]


def build_setup_experience() -> dict[str, Any]:
    return {
        "setup_experience": {
            "tone": "calm_premium_operational",
            "conversational": True,
            "progressive_disclosure": True,
            "not_a_numbered_wizard": True,
            "flow": FLOW,
            "operator_guidance": "AethOS guides — you stay in control. Every step explains what and why.",
            "phase": "phase4_step15",
            "bounded": True,
        }
    }
