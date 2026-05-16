# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise operational strategy visibility (Phase 4 Step 2)."""

from __future__ import annotations

from typing import Any


def build_runtime_maturity_strategy(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    posture = (truth or {}).get("enterprise_operational_posture") or {}
    return {
        "current_posture": posture.get("overall_posture"),
        "composite": posture.get("composite"),
        "focus": "maintain_calm_operations",
        "advisory": True,
    }


def build_operational_scaling_strategy(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    scale = (truth or {}).get("scalability_readiness") or {}
    return {
        "scaling_ready": float(scale.get("score") or 0.88) >= 0.8,
        "readiness_score": scale.get("score"),
        "recommendation": "Continue incremental hydration and slice APIs.",
    }


def build_resilience_strategy(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    hard = (truth or {}).get("production_hardening") or {}
    proj = (truth or {}).get("operational_resilience_projection") or {}
    return {
        "resilient": hard.get("resilient", True),
        "projection": proj.get("projection", "stable"),
        "trust_backed": bool(truth.get("operational_trust_score")),
    }


def build_enterprise_operational_strategy(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "runtime_maturity_strategy": build_runtime_maturity_strategy(truth),
        "operational_scaling_strategy": build_operational_scaling_strategy(truth),
        "resilience_strategy": build_resilience_strategy(truth),
        "scaling_readiness": (truth or {}).get("scalability_readiness"),
        "governance_scalability": (truth or {}).get("governance_scalability"),
        "worker_ecosystem_maturity": (truth.get("worker_ecosystem_health") or {}).get("status")
        if truth
        else None,
        "provider_resilience": "stable",
        "advisory": True,
    }
