# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime escalation visibility (Phase 3 Step 14)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state


def build_runtime_escalations(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    office = truth.get("office") or {}
    pressure = office.get("pressure") if isinstance(office, dict) else {}
    history: list[dict[str, Any]] = []

    if isinstance(pressure, dict):
        if pressure.get("deployment"):
            history.append({"type": "deployment_escalation", "severity": "high", "source": "office"})
        if pressure.get("retry"):
            history.append({"type": "retry_escalation", "severity": "medium", "source": "office"})
        if pressure.get("queue"):
            history.append({"type": "runtime_degradation_escalation", "severity": "medium", "source": "queue"})

    for sig in ((truth.get("operational_risk") or {}).get("risk_signals") or [])[:6]:
        if isinstance(sig, dict) and sig.get("severity") in ("high", "critical"):
            history.append(
                {
                    "type": "governance_escalation",
                    "severity": sig.get("severity"),
                    "what": sig.get("kind"),
                    "source": "workspace",
                }
            )

    routing = truth.get("routing_summary") or {}
    if routing.get("fallback_used"):
        history.append({"type": "provider_escalation", "severity": "medium", "source": "brain_router"})

    st = load_runtime_state()
    privacy = [e for e in (st.get("runtime_event_buffer") or []) if isinstance(e, dict) and e.get("category") == "privacy"]
    if len(privacy) > 3:
        history.append({"type": "privacy_escalation", "severity": "medium", "count": len(privacy)})

    for w in ((truth.get("runtime_workers") or {}).get("workers") or [])[:8]:
        if isinstance(w, dict) and str(w.get("status") or "").lower() in ("failed", "recovering"):
            history.append(
                {"type": "worker_escalation", "severity": "medium", "worker_id": w.get("agent_id"), "source": "worker"}
            )

    return {
        "active_escalations": history[:12],
        "escalation_count": len(history),
        "types_present": sorted({h.get("type") for h in history if h.get("type")}),
    }


def build_escalation_visibility(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    esc = build_runtime_escalations(truth)
    return {
        **esc,
        "explainable": True,
        "operator_readable": True,
    }


def build_escalation_history(truth: dict[str, Any] | None = None, *, limit: int = 24) -> list[dict[str, Any]]:
    return list((build_runtime_escalations(truth).get("active_escalations") or []))[:limit]
