# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime recovery integrity — explainable recovery history (Phase 4 Step 22)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state
from app.services.mission_control.runtime_restart_manager import build_runtime_restarts


def build_runtime_recovery_history(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    restarts = build_runtime_restarts(truth)
    history = list(restarts.get("restart_history") or [])[-16:]
    st = load_runtime_state()
    events = list((st.get("recovery") or {}).get("events") or [])[-16:]
    failover = list(st.get("routing_failover_history") or [])[-8:]
    combined: list[dict[str, Any]] = []
    for r in history:
        combined.append(
            {
                "kind": "runtime_restart",
                "when": r.get("at"),
                "ok": r.get("ok"),
                "message": "AethOS restarted runtime processes." if r.get("ok") else "Runtime restart needs review.",
            }
        )
    for f in failover:
        combined.append(
            {
                "kind": "provider_failover",
                "when": f.get("at"),
                "provider": f.get("provider"),
                "message": "AethOS recovered from a provider interruption.",
            }
        )
    for e in events:
        if isinstance(e, dict):
            combined.append({"kind": e.get("kind", "recovery"), "when": e.get("at"), "message": e.get("message")})
    return {
        "runtime_recovery_history": {
            "events": combined[-20:],
            "count": len(combined),
            "operator_action_required": any(not r.get("ok", True) for r in history[-3:]),
            "stable_now": not truth.get("runtime_ownership", {}).get("conflict"),
            "bounded": True,
        }
    }


def build_runtime_recovery_integrity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    hist = build_runtime_recovery_history(truth)["runtime_recovery_history"]
    categories = {
        "runtime_restart": any(e.get("kind") == "runtime_restart" for e in hist.get("events") or []),
        "provider_failover": any(e.get("kind") == "provider_failover" for e in hist.get("events") or []),
        "hydration_recovery": not bool((truth.get("hydration_progress") or {}).get("partial")),
        "ownership_recovery": not bool((truth.get("runtime_ownership") or {}).get("conflict")),
    }
    recovery_ux = []
    if categories.get("provider_failover"):
        recovery_ux.append(
            "AethOS restored runtime coordination after a temporary provider interruption."
        )
    if not categories.get("hydration_recovery"):
        recovery_ux.append("AethOS resumed enterprise intelligence after recovering hydration state.")
    return {
        "runtime_recovery_integrity": {
            "categories_tracked": list(categories.keys()),
            "categories_active": [k for k, v in categories.items() if v],
            "explainable": True,
            "operator_visibility": "full",
            "stable": hist.get("stable_now"),
            "operator_action_required": hist.get("operator_action_required"),
            "recovery_ux_messages": recovery_ux,
            "confidence_updates_readiness": True,
            "mission_control_reflects_stabilized": hist.get("stable_now"),
            "phase": "phase4_step23",
            "bounded": True,
        }
    }
