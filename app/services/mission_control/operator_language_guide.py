# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Standard operator-facing terminology (Phase 4 Step 20)."""

from __future__ import annotations

from typing import Any

PREFERRED_TERMS = {
    "orchestrator": "AethOS coordinates workers and providers",
    "runtime": "Operational execution environment",
    "operational_health": "Current system posture",
    "readiness": "Progressive startup availability",
    "recovery": "Safe restoration after degradation",
    "supervision": "Process and lock coordination",
    "continuity": "Operational memory across sessions",
    "governance": "Accountability timeline",
    "provider_routing": "Advisory provider selection",
}

AVOID_TERMS = ("Nexa", "OpenClaw", "ClawHub", "OpenHub", "white screen", "internal server error")


def build_operator_language_guide() -> dict[str, Any]:
    return {
        "operator_language_guide": {
            "preferred_terms": PREFERRED_TERMS,
            "avoid_terms": list(AVOID_TERMS),
            "calm_copy_rule": "Prefer clear operational guidance over raw failure noise",
            "phase": "phase4_step20",
            "bounded": True,
        }
    }
