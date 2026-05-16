# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Persistent operational memory intelligence (Phase 4 Step 5)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state


def build_provider_operational_history(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    st = load_runtime_state()
    return {
        "provider_actions": list(st.get("operator_provider_actions") or [])[-8:],
        "routing_history": list(st.get("routing_failover_history") or [])[-8:],
    }


def build_deployment_learning(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    st = load_runtime_state()
    return {
        "deployment_traces": list(st.get("deployment_traces") or [])[-6:] if isinstance(st.get("deployment_traces"), list) else [],
        "readiness": (truth or {}).get("deployment_readiness"),
    }


def build_worker_specialization_memory(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "specialization_map": (truth or {}).get("worker_specialization_map"),
        "ecosystem_health": (truth or {}).get("worker_ecosystem_health"),
    }


def build_continuity_learning(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    c = (truth or {}).get("operator_continuity") or (truth or {}).get("continuity_memory") or {}
    return {"continuity_available": bool(c), "snapshot": c if isinstance(c, dict) else {}}


def build_strategic_operational_memory(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "provider_operational_history": build_provider_operational_history(truth),
        "deployment_learning": build_deployment_learning(truth),
        "worker_specialization_memory": build_worker_specialization_memory(truth),
        "continuity_learning": build_continuity_learning(truth),
        "bounded": True,
        "searchable": True,
    }


def build_operational_memory_intelligence(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    mem = build_strategic_operational_memory(truth)
    esc = int(((truth or {}).get("runtime_escalations") or {}).get("escalation_count") or 0)
    return {
        "strategic_operational_memory": mem,
        **mem,
        "answers": {
            "what_usually_fails": "check degradation_signals and repair contexts",
            "provider_best_for_project": "derived from routing_failover_history",
            "retry_loop_risk": esc > 2,
        },
    }
