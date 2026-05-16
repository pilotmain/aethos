# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise operational memory — bounded evolution history (Phase 4 Step 1)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_MAX_HISTORY = 32


def _append_evolution(entry: dict[str, Any]) -> None:
    st = load_runtime_state()
    hist = st.setdefault("runtime_evolution_history", [])
    if isinstance(hist, list):
        hist.append({**entry, "at": utc_now_iso()})
        if len(hist) > _MAX_HISTORY:
            del hist[: len(hist) - _MAX_HISTORY]
    save_runtime_state(st)


def build_enterprise_operational_memory(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    st = load_runtime_state()
    _append_evolution(
        {
            "readiness": truth.get("runtime_readiness_score"),
            "trust": truth.get("operational_trust_score"),
        }
    )
    return {
        "deployment_histories": _bounded_tail(st.get("deployment_traces"), 12),
        "provider_histories": _bounded_tail(st.get("operator_provider_actions"), 12),
        "governance_histories": _bounded_tail(st.get("plugin_governance_audit"), 8),
        "continuity_histories": [truth.get("operator_continuity")] if truth.get("operator_continuity") else [],
        "escalation_histories": (truth.get("runtime_escalations") or {}).get("active_escalations") or [],
        "searchable": True,
        "bounded": True,
        "privacy_aware": True,
    }


def build_operational_history_quality(
    truth: dict[str, Any] | None = None,
    *,
    memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mem = memory if memory is not None else build_enterprise_operational_memory(truth)
    sections = sum(1 for k in ("deployment_histories", "provider_histories", "governance_histories") if mem.get(k))
    return {"coverage_score": round(sections / 3.0, 3), "sections_populated": sections}


def build_continuity_memory(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    c = (truth or {}).get("operator_continuity") or {}
    return {"snapshot": c, "resume_available": c.get("resume_available") if isinstance(c, dict) else False}


def build_runtime_evolution_history() -> list[dict[str, Any]]:
    st = load_runtime_state()
    hist = st.get("runtime_evolution_history") or []
    return list(hist)[-16:] if isinstance(hist, list) else []


def _bounded_tail(val: Any, n: int) -> list[Any]:
    if isinstance(val, list):
        return list(val)[-n:]
    return []
