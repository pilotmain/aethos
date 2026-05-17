# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Final enterprise confidence convergence (Phase 4 Step 27)."""

from __future__ import annotations

from typing import Any

CONFIDENCE_CATEGORIES = (
    "operational_confidence",
    "readiness_confidence",
    "recovery_confidence",
    "stability_confidence",
    "governance_confidence",
    "continuity_confidence",
    "trust_confidence",
)


def build_runtime_enterprise_confidence_engine(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    scores: dict[str, float] = {
        "operational_confidence": float((truth.get("operator_confidence") or {}).get("score") or 0.85),
        "readiness_confidence": float(truth.get("runtime_readiness_score") or 0.8),
        "recovery_confidence": 0.9 if truth.get("runtime_recovery_certified") else 0.7,
        "stability_confidence": 0.92 if truth.get("runtime_operationally_stable") else 0.75,
        "governance_confidence": 0.93 if truth.get("enterprise_runtime_governed") else 0.72,
        "continuity_confidence": float(
            (truth.get("runtime_operator_continuity_confidence") or {}).get("score") or 0.85
        ),
        "trust_confidence": float((truth.get("runtime_trust_finalization") or {}).get("trust_score") or 0.85),
    }
    overall = round(sum(scores.values()) / max(1, len(scores)), 3)
    locked = overall >= 0.85
    return {
        "runtime_enterprise_confidence_engine": {
            "phase": "phase4_step27",
            "categories": scores,
            "confidence_score": overall,
            "enterprise_operator_confidence_locked": locked,
            "runtime_enterprise_confidence_verified": locked,
            "bounded": True,
        },
        "enterprise_operator_confidence_locked": locked,
        "runtime_enterprise_confidence_verified": locked,
    }
