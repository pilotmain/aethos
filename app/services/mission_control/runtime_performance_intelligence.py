# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime performance intelligence (Phase 4 Step 7)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_hydration import get_hydration_metrics


def build_runtime_performance_intelligence(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    hm = get_hydration_metrics()
    perf = truth.get("runtime_performance") or {}
    discipline = truth.get("payload_discipline") or {}
    hits = int(hm.get("slice_cache_hits") or 0)
    misses = int(hm.get("slice_cache_misses") or 0)
    total = hits + misses
    hit_rate = round(hits / max(1, total), 4)

    slowest = []
    for name, ms in (hm.get("slice_build_times") or {}).items():
        if isinstance(ms, (int, float)) and ms > 500:
            slowest.append({"builder": name, "duration_ms": ms})

    cold = int(hm.get("cold_start_count") or 0)
    if perf and not hm.get("cache_hit_rate"):
        cold = cold + 1

    recommendations = []
    if hit_rate < 0.85:
        recommendations.append(
            {"title": "Improve slice cache warmth", "detail": "Cache hit rate below 85% target.", "advisory_only": True}
        )
    if slowest:
        recommendations.append(
            {
                "title": "Review slow hydration builders",
                "detail": f"Slowest: {slowest[0].get('builder')}",
                "advisory_only": True,
            }
        )

    return {
        "hydration_bottlenecks": slowest[:6],
        "slowest_builders": slowest[:6],
        "cache_efficiency": {"hit_rate": hit_rate, "hits": hits, "misses": misses},
        "payload_pressure": discipline,
        "panel_responsiveness": truth.get("operational_responsiveness") or {},
        "degraded_path_frequency": truth.get("runtime_resilience", {}).get("connection_repair_attempts"),
        "cold_start_frequency": cold,
        "operational_responsiveness_score": round(min(1.0, hit_rate * 0.6 + (0.4 if not slowest else 0.2)), 3),
        "top_bottlenecks": slowest[:3],
        "recommendations": recommendations[:5],
        "optimization_opportunities": recommendations[:5],
    }
