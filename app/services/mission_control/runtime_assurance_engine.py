# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise runtime assurance engine (Phase 4 Step 23)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.operator_confidence_engine import build_operator_confidence
from app.services.mission_control.runtime_operational_authority import build_runtime_operational_authority
from app.services.mission_control.runtime_readiness_authority import build_runtime_readiness_authority


def build_runtime_assurance_engine(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    readiness = build_runtime_readiness_authority(truth)["runtime_readiness_authority"]
    authority = build_runtime_operational_authority(truth)
    confidence = build_operator_confidence(truth)
    partial = bool((truth.get("hydration_progress") or {}).get("partial"))
    safe = readiness.get("safe_for_operator", False)
    stable = readiness.get("state") == "operational" and not partial
    summary = confidence["operator_confidence"]["summary"]
    return {
        "runtime_assurance": {
            "safe": safe,
            "stable": stable,
            "data_stale": authority["operational_authority"].get("data_stale"),
            "hydration_partial": partial,
            "manual_action_needed": bool((truth.get("runtime_recovery_integrity") or {}).get("operator_action_required")),
            "summary": summary,
            "bounded": True,
        },
        "enterprise_assurance": {
            "enterprise_ready": readiness.get("enterprise_ready"),
            "synchronized": stable,
            "bounded": True,
        },
        "operational_assurance": {
            "authoritative": authority["operational_authority"].get("authoritative"),
            "degraded_mode": authority["operational_authority"].get("degraded_mode"),
            "bounded": True,
        },
        "recovery_assurance": {
            "stable": (truth.get("runtime_recovery_integrity") or {}).get("stable", True),
            "recovery_succeeded": not (truth.get("runtime_recovery_integrity") or {}).get("operator_action_required"),
            "bounded": True,
        },
        "continuity_assurance": {"continuous": True, "bounded": True},
        "hydration_assurance": {
            "partial": partial,
            "message": (
                "Advanced operational analysis is still warming. Core orchestration is already available."
                if partial
                else "Hydration complete."
            ),
            "bounded": True,
        },
        "routing_assurance": {
            "fallback_occurred": bool((truth.get("routing_summary") or {}).get("fallback_used")),
            "bounded": True,
        },
        "provider_assurance": {"primary": (truth.get("routing_summary") or {}).get("primary_provider"), "bounded": True},
        "phase": "phase4_step23",
        "bounded": True,
    }
