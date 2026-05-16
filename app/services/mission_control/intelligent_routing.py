# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Intelligent dynamic model routing — advisory, explainable (Phase 4 Step 5)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_MAX_ROUTING_HISTORY = 24


def _append_routing_history(entry: dict[str, Any]) -> None:
    st = load_runtime_state()
    hist = st.setdefault("routing_failover_history", [])
    if isinstance(hist, list):
        hist.append({**entry, "at": utc_now_iso()})
        if len(hist) > _MAX_ROUTING_HISTORY:
            del hist[: len(hist) - _MAX_ROUTING_HISTORY]
        st["routing_failover_history"] = hist
    save_runtime_state(st)


def build_adaptive_provider_selection(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    routing = truth.get("routing_summary") or {}
    mode = truth.get("AETHOS_ROUTING_MODE") or (truth.get("adaptive_operational_learning") or {}).get("learning_mode")
    return {
        "primary_provider": routing.get("primary_provider"),
        "fallback_used": routing.get("fallback_used"),
        "local_first": truth.get("AETHOS_LOCAL_FIRST") == "true" or truth.get("AETHOS_LOCAL_FIRST") is True,
        "mode": mode or "advisory_only",
        "advisory": True,
    }


def build_runtime_provider_strategy(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    pref = truth.get("AETHOS_ROUTING_PREFERENCE") or "balanced"
    return {
        "preference": pref,
        "layers": ["strategic", "tactical", "fallback", "privacy", "continuity"],
        "require_paid_approval": truth.get("AETHOS_ROUTING_REQUIRE_PAID_APPROVAL") == "true",
        "advisory": True,
    }


def build_routing_effectiveness(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    routing = (truth or {}).get("routing_summary") or {}
    return {
        "fallback_rate": 1.0 if routing.get("fallback_used") else 0.0,
        "provider_confidence": 0.85 if not routing.get("fallback_used") else 0.65,
        "task_capability_score": 0.8,
    }


def build_routing_governance(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "orchestrator_owned": True,
        "no_hidden_routing": True,
        "operator_review_required": True,
        "explainable": True,
    }


def record_routing_hydration_event(truth: dict[str, Any] | None = None) -> None:
    """Persist one bounded routing event per hydration (orchestrator-visible)."""
    truth = truth or {}
    routing = truth.get("routing_summary") or {}
    _append_routing_history(
        {
            "reason": "hydration",
            "fallback": routing.get("fallback_used"),
            "provider": routing.get("primary_provider"),
        }
    )


def build_intelligent_routing(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    selection = build_adaptive_provider_selection(truth)
    st = load_runtime_state()
    hist = list(st.get("routing_failover_history") or [])[-8:]
    return {
        "advisory_first": True,
        "adaptive_provider_selection": selection,
        "runtime_provider_strategy": build_runtime_provider_strategy(truth),
        "routing_effectiveness": build_routing_effectiveness(truth),
        "routing_governance": build_routing_governance(truth),
        "routing_failover_history": hist,
        "routing_reason": "runtime_derived",
        "routing_metadata": {
            "routing_reason": "task_and_pressure_derived",
            "provider_confidence": build_routing_effectiveness(truth).get("provider_confidence"),
        },
    }
