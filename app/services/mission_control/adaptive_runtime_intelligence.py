# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Adaptive operational intelligence — advisory, explainable (Phase 4 Step 1)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso


def _record_adaptation(entry: dict[str, Any]) -> None:
    st = load_runtime_state()
    hist = st.setdefault("runtime_adaptation_history", [])
    if isinstance(hist, list):
        hist.append({**entry, "at": utc_now_iso()})
        if len(hist) > 48:
            del hist[: len(hist) - 48]
        st["runtime_adaptation_history"] = hist
    save_runtime_state(st)


def build_operational_optimization_signals(truth: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    truth = truth or {}
    signals: list[dict[str, Any]] = []
    pressure = truth.get("operational_pressure") or {}
    if pressure.get("queue_pressure"):
        signals.append(
            {
                "domain": "runtime_pressure",
                "priority": "high",
                "suggestion": "Reduce concurrent queue depth or stagger worker assignments.",
                "advisory": True,
            }
        )
    routing = truth.get("routing_summary") or {}
    if routing.get("fallback_used"):
        signals.append(
            {
                "domain": "provider_routing",
                "priority": "medium",
                "suggestion": "Review provider fallback — consider primary provider health check.",
                "advisory": True,
            }
        )
    recs = ((truth.get("runtime_recommendations") or {}).get("recommendations") or [])[:3]
    for r in recs:
        if isinstance(r, dict):
            signals.append(
                {
                    "domain": "recommendation",
                    "priority": r.get("operational_impact", "medium"),
                    "suggestion": r.get("suggested_next_step") or r.get("message"),
                    "advisory": True,
                }
            )
    return signals[:12]


def build_adaptive_operational_learning(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    st = load_runtime_state()
    hist = st.get("runtime_adaptation_history") or []
    trust = float(truth.get("operational_trust_score") or 0.8)
    calm = float((truth.get("runtime_calmness") or {}).get("calm_score") or 0.7)
    return {
        "adaptation_cycles": len(hist) if isinstance(hist, list) else 0,
        "trust_trend": "stable" if trust >= 0.75 else "review",
        "calmness_trend": "stable" if calm >= 0.7 else "elevated",
        "learning_mode": "advisory_only",
        "operator_review_required": True,
    }


def build_adaptive_runtime_intelligence(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    signals = build_operational_optimization_signals(truth)
    learning = build_adaptive_operational_learning(truth)
    _record_adaptation({"signal_count": len(signals), "mode": "hydration"})
    st = load_runtime_state()
    hist = list(st.get("runtime_adaptation_history") or [])[-16:]
    return {
        "advisory_first": True,
        "explainable": True,
        "runtime_visible": True,
        "optimization_signals": signals,
        "adaptive_operational_learning": learning,
        "operational_optimization_signals": signals,
        "runtime_adaptation_history": hist,
        "domains": sorted({s.get("domain") for s in signals if s.get("domain")}),
    }
