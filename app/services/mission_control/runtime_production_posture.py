# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise runtime production posture (Phase 4 Step 8)."""

from __future__ import annotations

from typing import Any


def build_production_runtime_posture(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    perf = truth.get("runtime_performance_intelligence") or {}
    resilience = truth.get("runtime_resilience") or {}
    integrity = truth.get("runtime_truth_integrity") or {}
    score = float(perf.get("operational_responsiveness_score") or 0.8)
    sustained = round(
        min(
            1.0,
            score * 0.4
            + float(integrity.get("truth_integrity_score") or 0.85) * 0.3
            + (0.3 if resilience.get("status") == "healthy" else 0.15),
        ),
        3,
    )
    return {
        "production_runtime_posture": {
            "ready": sustained >= 0.75,
            "office_resilience": resilience.get("status") == "healthy",
            "governance_resilience": bool(truth.get("governance_operational_index")),
            "continuity_resilience": bool(truth.get("operational_continuity_engine")),
            "provider_ecosystem_resilience": bool(truth.get("routing_summary")),
        },
        "sustained_operation_score": sustained,
        "enterprise_resilience": {
            "scalability": (truth.get("runtime_scalability_health") or {}).get("status"),
            "throttling": (truth.get("runtime_operational_throttling") or {}).get("active"),
        },
        "operational_scalability_posture": truth.get("runtime_scalability_health"),
        "runtime_operational_readiness": truth.get("runtime_readiness_score"),
    }
