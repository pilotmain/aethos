# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Long-horizon runtime continuity — bounded eras (Phase 4 Step 8)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_MAX_ERAS = 16
_MAX_WINDOWS = 24


def build_operational_eras(truth: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    truth = truth or {}
    readiness = truth.get("runtime_readiness_score")
    return [
        {
            "era": "current",
            "summary": (truth.get("operational_narratives") or {}).get("headline") or "current operations",
            "readiness": readiness,
            "at": utc_now_iso(),
        }
    ]


def build_runtime_history_windows(truth: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    st = load_runtime_state()
    hist = list(st.get("runtime_evolution_history") or [])[-8:]
    return [{"window": i, "event": e} for i, e in enumerate(hist) if isinstance(e, dict)][:_MAX_WINDOWS]


def build_governance_eras(truth: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    truth = truth or {}
    esc = int((truth.get("runtime_escalations") or {}).get("escalation_count") or 0)
    return [{"era": "recent", "escalations": esc, "accountability": True}]


def build_enterprise_memory_timeline(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "continuity_memory": bool(truth.get("continuity_memory")),
        "strategic_memory": bool(truth.get("strategic_operational_memory")),
        "bounded": True,
        "reconstructable": True,
    }


def build_runtime_long_horizon(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    eras = build_operational_eras(truth)
    st = load_runtime_state()
    bucket = st.setdefault("runtime_long_horizon", {})
    if isinstance(bucket, dict):
        bucket["eras"] = eras[-_MAX_ERAS:]
        bucket["updated_at"] = utc_now_iso()
        st["runtime_long_horizon"] = bucket
        save_runtime_state(st)
    return {
        "operational_eras": eras,
        "runtime_history_windows": build_runtime_history_windows(truth),
        "governance_eras": build_governance_eras(truth),
        "enterprise_memory_timeline": build_enterprise_memory_timeline(truth),
        "bounded": True,
        "explainable": True,
    }
