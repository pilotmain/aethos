# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Final enterprise runtime trust convergence (Phase 4 Step 26)."""

from __future__ import annotations

from typing import Any

TRUST_CATEGORIES = (
    "runtime_stability_trust",
    "runtime_recovery_trust",
    "runtime_readiness_trust",
    "runtime_responsiveness_trust",
    "runtime_governance_trust",
    "runtime_operational_trust",
    "runtime_operator_confidence",
)


def build_runtime_trust_finalization(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    scores: dict[str, float] = {
        "runtime_stability_trust": float((truth.get("runtime_stability") or {}).get("score") or 0.88),
        "runtime_recovery_trust": 0.92 if truth.get("runtime_recovery_certified") else 0.7,
        "runtime_readiness_trust": float(truth.get("runtime_readiness_score") or 0.85),
        "runtime_responsiveness_trust": float(
            (truth.get("runtime_responsiveness_guarantees") or {}).get("score") or 0.85
        ),
        "runtime_governance_trust": 0.95 if truth.get("enterprise_runtime_governed") else 0.72,
        "runtime_operational_trust": 0.93 if truth.get("runtime_operationally_trusted") else 0.75,
        "runtime_operator_confidence": float((truth.get("operator_confidence") or {}).get("score") or 0.85),
    }
    overall = round(sum(scores.values()) / max(1, len(scores)), 3)
    trusted = overall >= 0.85 and truth.get("launch_stabilized")
    return {
        "runtime_trust_finalization": {
            "phase": "phase4_step26",
            "categories": scores,
            "trust_score": overall,
            "enterprise_runtime_trusted": trusted,
            "runtime_operator_confidence_verified": scores["runtime_operator_confidence"] >= 0.8,
            "enterprise_operational_trust_locked": trusted,
            "bounded": True,
        },
        "enterprise_runtime_trusted": trusted,
        "runtime_operator_confidence_verified": scores["runtime_operator_confidence"] >= 0.8,
        "enterprise_operational_trust_locked": trusted,
    }
