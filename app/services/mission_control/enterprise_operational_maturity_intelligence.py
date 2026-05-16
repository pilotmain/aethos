# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Ecosystem operational maturity intelligence (Phase 4 Step 3)."""

from __future__ import annotations

from typing import Any


def build_ecosystem_operational_maturity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    eco = (truth or {}).get("ecosystem_maturity") or {}
    health = (truth or {}).get("ecosystem_operational_health") or {}
    return {
        "ecosystem_composite": eco.get("composite") or health.get("composite_health"),
        "worker": (truth or {}).get("worker_ecosystem_maturity"),
        "automation": (truth.get("automation_operational_effectiveness") or {}).get("success_rate") if truth else None,
        "governance": (truth.get("governance_readiness") or {}).get("score") if truth else None,
    }


def build_enterprise_intelligence_maturity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    strat = (truth or {}).get("strategic_operational_maturity") or {}
    return {
        "intelligence_depth": strat.get("intelligence_depth", 0),
        "forecasting_enabled": bool(truth.get("adaptive_operational_forecasting")),
        "ecosystem_coordinated": bool(truth.get("operational_intelligence_ecosystem")),
    }


def build_strategic_operational_resilience(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    res = (truth or {}).get("operational_resilience_projection") or {}
    hard = (truth or {}).get("production_hardening") or {}
    return {
        "resilient": res.get("resilient", hard.get("resilient", True)),
        "projection": res.get("projection", "stable"),
        "trust_backed": bool(truth.get("operational_trust_score")),
    }


def build_adaptive_operational_maturity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ecosystem_operational_maturity": build_ecosystem_operational_maturity(truth),
        "enterprise_intelligence_maturity": build_enterprise_intelligence_maturity(truth),
        "strategic_operational_resilience": build_strategic_operational_resilience(truth),
        "optimization_maturity": (truth or {}).get("runtime_optimization_quality"),
    }
