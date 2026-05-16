# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Adaptive runtime optimization — advisory, bounded (Phase 4 Step 3)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_MAX_OPT_HISTORY = 32


def _record_optimization(entry: dict[str, Any]) -> None:
    st = load_runtime_state()
    hist = st.setdefault("runtime_optimization_history", [])
    if isinstance(hist, list):
        hist.append({**entry, "at": utc_now_iso()})
        if len(hist) > _MAX_OPT_HISTORY:
            del hist[: len(hist) - _MAX_OPT_HISTORY]
        st["runtime_optimization_history"] = hist
    save_runtime_state(st)


def build_operational_efficiency_signals(truth: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    truth = truth or {}
    signals: list[dict[str, Any]] = []
    perf = truth.get("runtime_performance") or {}
    if perf.get("cache_hit_rate") and float(perf["cache_hit_rate"]) < 0.3:
        signals.append(
            {
                "domain": "hydration_efficiency",
                "suggestion": "Warm slice cache — reuse lightweight MC endpoints.",
                "advisory": True,
            }
        )
    for sig in (truth.get("operational_optimization_signals") or [])[:4]:
        if isinstance(sig, dict):
            signals.append({**sig, "optimization_context": True})
    pressure = truth.get("operational_pressure") or {}
    if pressure.get("level") == "high":
        signals.append(
            {
                "domain": "runtime_pressure",
                "suggestion": "Prioritize continuity and defer non-critical automation.",
                "priority": "high",
                "advisory": True,
            }
        )
    return signals[:12]


def build_runtime_optimization_quality(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    coord = (truth.get("coordination_quality") or {}).get("score", 0.75)
    eff = (truth.get("workflow_efficiency") or {}).get("efficient", False)
    score = float(coord) * (1.05 if eff else 1.0)
    return {
        "score": round(min(1.0, score), 3),
        "coordination_backed": True,
        "advisory": True,
    }


def build_adaptive_runtime_optimization(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    signals = build_operational_efficiency_signals(truth)
    _record_optimization({"signal_count": len(signals), "mode": "hydration"})
    st = load_runtime_state()
    hist = list(st.get("runtime_optimization_history") or [])[-12:]
    return {
        "advisory_first": True,
        "explainable": True,
        "governance_aware": True,
        "operational_efficiency_signals": signals,
        "optimization_domains": sorted({s.get("domain") for s in signals if s.get("domain")}),
    }
