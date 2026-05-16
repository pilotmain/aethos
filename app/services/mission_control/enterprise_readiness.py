# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise and operational readiness scores (Phase 3 Step 16)."""

from __future__ import annotations

from typing import Any


def _score(*parts: float) -> float:
    if not parts:
        return 0.0
    return round(max(0.0, min(1.0, sum(parts) / len(parts))), 3)


def build_deployment_readiness(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    health = str((truth.get("enterprise_operational_health") or {}).get("overall") or "healthy")
    pressure = (truth.get("operational_pressure") or {}).get("deployment_pressure")
    score = 0.85 if health in ("healthy", "recovering") and not pressure else 0.55
    return {"score": score, "health": health, "deployment_pressure": bool(pressure)}


def build_governance_readiness(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    tl = truth.get("unified_operational_timeline") or {}
    gov = truth.get("governance_integrity") or {}
    score = 0.9 if tl.get("authoritative") else 0.5
    if isinstance(gov, dict) and gov.get("integrity") == "review":
        score -= 0.1
    return {"score": round(max(0.0, score), 3), "authoritative_timeline": tl.get("authoritative")}


def build_scalability_readiness(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    disc = truth.get("payload_discipline") or {}
    scale = truth.get("runtime_scalability_health") or {}
    within = disc.get("within_budget", True)
    score = 0.88 if within else 0.5
    if str(scale.get("status") or "") == "elevated":
        score -= 0.15
    return {"score": round(max(0.35, score), 3), "payload_within_budget": within}


def build_operational_readiness(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    trust = float(truth.get("operational_trust_score") or 0.75)
    calm = float((truth.get("runtime_calmness") or {}).get("calm_score") or 0.7)
    quality = float((truth.get("operational_quality") or {}).get("quality_score") or 0.75)
    score = _score(trust, calm, quality)
    return {
        "score": score,
        "trust": trust,
        "calmness": calm,
        "quality": quality,
        "enterprise_ready": score >= 0.75,
    }


def build_runtime_readiness_score(truth: dict[str, Any] | None = None) -> float:
    op = build_operational_readiness(truth)
    dep = build_deployment_readiness(truth)
    gov = build_governance_readiness(truth)
    scale = build_scalability_readiness(truth)
    perf = truth or {}
    hydration_ok = float((perf.get("runtime_performance") or {}).get("hydration_latency_ms") or 0) < 5000
    perf_score = 0.85 if hydration_ok else 0.6
    return _score(
        float(op.get("score") or 0),
        float(dep.get("score") or 0),
        float(gov.get("score") or 0),
        float(scale.get("score") or 0),
        perf_score,
    )


def build_enterprise_readiness(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "runtime_readiness_score": build_runtime_readiness_score(truth),
        "operational_readiness": build_operational_readiness(truth),
        "deployment_readiness": build_deployment_readiness(truth),
        "governance_readiness": build_governance_readiness(truth),
        "scalability_readiness": build_scalability_readiness(truth),
        "enterprise_ready": build_runtime_readiness_score(truth) >= 0.78,
        "production_grade": build_runtime_readiness_score(truth) >= 0.72,
    }
