# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Ecosystem operational strategy (Phase 4 Step 3)."""

from __future__ import annotations

from typing import Any


def build_enterprise_ecosystem_outlook(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    health = (truth or {}).get("ecosystem_operational_health") or {}
    outlook = (truth or {}).get("enterprise_operational_outlook") or {}
    return {
        "outlook": outlook.get("outlook", health.get("status", "stable")),
        "summary": outlook.get("summary"),
        "composite_health": health.get("composite_health"),
    }


def build_operational_ecosystem_health(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = (truth or {}).get("ecosystem_operational_health")
    if existing:
        return existing
    from app.services.mission_control.operational_intelligence_ecosystem import build_ecosystem_operational_health

    return build_ecosystem_operational_health(truth)


def build_strategic_ecosystem_projection(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    mat = (truth or {}).get("ecosystem_maturity_progression") or {}
    return {
        "direction": mat.get("direction", "progressing"),
        "scaling_ready": ((truth or {}).get("scalability_readiness") or {}).get("score", 0.88) >= 0.8,
        "advisory": True,
    }


def build_ecosystem_operational_strategy(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "enterprise_ecosystem_outlook": build_enterprise_ecosystem_outlook(truth),
        "operational_ecosystem_health": build_operational_ecosystem_health(truth),
        "strategic_ecosystem_projection": build_strategic_ecosystem_projection(truth),
        "worker_ecosystem_evolution": (truth or {}).get("worker_ecosystem_maturity"),
        "governance_ecosystem_maturity": (truth or {}).get("governance_maturity_progression"),
        "advisory": True,
    }
