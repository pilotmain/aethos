# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operational intelligence ecosystem coordination (Phase 4 Step 3)."""

from __future__ import annotations

from typing import Any


def _ecosystem_health_score(truth: dict[str, Any], key: str, default: float = 0.8) -> float:
    block = truth.get(key) or {}
    if isinstance(block, dict):
        for field in ("health_score", "score", "success_rate", "reliability"):
            if block.get(field) is not None:
                return float(block[field])
    return default


def build_ecosystem_coordination(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "worker_ecosystem": (truth.get("worker_ecosystem_health") or {}).get("status"),
        "provider_ecosystem": "stable",
        "governance_ecosystem": (truth.get("governance_maturity_progression") or {}).get("direction"),
        "automation_ecosystem": (truth.get("automation_operational_effectiveness") or {}).get("success_rate"),
        "continuity_ecosystem": bool(truth.get("operator_continuity")),
        "orchestrator_owned": True,
    }


def build_ecosystem_operational_health(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    worker = _ecosystem_health_score(truth, "worker_ecosystem_health")
    auto = _ecosystem_health_score(truth, "automation_operational_effectiveness", 0.85)
    gov = float((truth.get("governance_readiness") or {}).get("score") or 0.85)
    composite = round((worker + auto + gov) / 3, 3)
    return {
        "composite_health": composite,
        "status": "healthy" if composite >= 0.78 else "review",
        "domains": ["worker", "provider", "governance", "deployment", "automation", "continuity", "trust"],
    }


def build_ecosystem_maturity_progression(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    eco = (truth or {}).get("ecosystem_maturity") or {}
    return {
        "current_composite": eco.get("composite"),
        "direction": "progressing",
        "advisory": True,
    }


def build_operational_intelligence_ecosystem(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ecosystem_coordination": build_ecosystem_coordination(truth),
        "ecosystem_operational_health": build_ecosystem_operational_health(truth),
        "ecosystem_maturity_progression": build_ecosystem_maturity_progression(truth),
        "bounded": True,
        "explainable": True,
    }
