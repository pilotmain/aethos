# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime evolution memory — bounded progression history (Phase 4 Step 2)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_MAX_PATTERNS = 24


def _record_growth_pattern(entry: dict[str, Any]) -> None:
    st = load_runtime_state()
    patterns = st.setdefault("runtime_growth_patterns", [])
    if isinstance(patterns, list):
        patterns.append({**entry, "at": utc_now_iso()})
        if len(patterns) > _MAX_PATTERNS:
            del patterns[: len(patterns) - _MAX_PATTERNS]
        st["runtime_growth_patterns"] = patterns
    save_runtime_state(st)


def build_operational_progression(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "readiness": truth.get("runtime_readiness_score"),
        "trust": truth.get("operational_trust_score"),
        "maturity": (truth.get("enterprise_operational_posture") or {}).get("overall_posture"),
        "trend": (truth.get("operational_trajectory_summary") or {}).get("direction"),
    }


def build_enterprise_operational_history(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    st = load_runtime_state()
    return {
        "evolution_history": list(st.get("runtime_evolution_history") or [])[-12:],
        "adaptation_history": list(st.get("runtime_adaptation_history") or [])[-12:],
        "bounded": True,
    }


def build_runtime_growth_patterns(truth: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    truth = truth or {}
    _record_growth_pattern(
        {
            "readiness": truth.get("runtime_readiness_score"),
            "worker_health": (truth.get("worker_ecosystem_health") or {}).get("health_score"),
        }
    )
    st = load_runtime_state()
    patterns = st.get("runtime_growth_patterns") or []
    return list(patterns)[-16:] if isinstance(patterns, list) else []


def build_runtime_evolution_memory(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "worker_evolution": (truth or {}).get("worker_learning_state"),
        "governance_progression": (truth or {}).get("governance_maturity_progression"),
        "deployment_maturity": (truth or {}).get("deployment_readiness"),
        "automation_evolution": (truth or {}).get("automation_adaptation"),
        "operational_progression": build_operational_progression(truth),
        "enterprise_operational_history": build_enterprise_operational_history(truth),
        "runtime_growth_patterns": build_runtime_growth_patterns(truth),
        "bounded": True,
        "searchable": True,
    }
