# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise operator trust experience (Phase 4 Step 12)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.mission_control_language_system import translate_term


def build_enterprise_operator_trust(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    resilience = truth.get("runtime_resilience") or {}
    return {
        "enterprise_operator_trust": {
            "calm": True,
            "explainable": True,
            "transparent": True,
            "premium_tone": True,
            "trust_score": truth.get("operational_trust_score"),
        },
        "operational_messages": {
            "connection_unavailable": "Runtime connection unavailable. AethOS is attempting recovery.",
            "degraded": translate_term("degraded", fallback="Needs attention") + " — advisory recommendations available.",
            "recovery": "Operational recovery active under orchestrator supervision.",
            "throttling": translate_term("throttling") + " — protecting Mission Control responsiveness.",
        },
        "explainability_coverage": [
            "routing",
            "recommendations",
            "recovery",
            "throttling",
            "continuity",
            "governance",
            "worker_lifecycle",
        ],
        "resilience_status": resilience.get("status"),
        "bounded": True,
    }
