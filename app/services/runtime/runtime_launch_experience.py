# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime launch experience — unified startup clarity (Phase 4 Step 28)."""

from __future__ import annotations

from typing import Any

from app.services.runtime.runtime_launch_orchestration import (
    UNIFIED_LAUNCH_STAGES,
    derive_operator_readiness_state,
    launch_stages_as_dicts,
)

LAUNCH_STAGES = launch_stages_as_dicts()


def build_runtime_launch_experience(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    readiness = truth.get("runtime_readiness_convergence") or {}
    pct = float(readiness.get("canonical_score") or 0.4)
    idx = min(len(LAUNCH_STAGES) - 1, int(pct * (len(LAUNCH_STAGES) - 1)))
    current = LAUNCH_STAGES[idx]
    api_ok = bool((truth.get("runtime_launch_integrity") or {}).get("api_reachable"))
    mc_ok = bool((truth.get("runtime_launch_integrity") or {}).get("mission_control_reachable"))
    op_state = derive_operator_readiness_state(
        api_reachable=api_ok,
        mc_reachable=mc_ok,
        hydration_partial=bool((truth.get("hydration_progress") or {}).get("partial")),
    )
    truly_ready = op_state == "operational"
    return {
        "runtime_launch_experience": {
            "phase": "phase4_step30",
            "current_stage": current,
            "stages": LAUNCH_STAGES,
            "truly_operational": truly_ready,
            "operator_readiness_state": op_state,
            "message": (
                "AethOS is operational."
                if truly_ready
                else "AethOS is preparing operational services…"
            ),
            "bounded": True,
        },
        "runtime_launch_progress": {
            "phase": "phase4_step28",
            "percent": round(pct, 3),
            "stage_index": idx,
            "bounded": True,
        },
        "runtime_launch_readiness": {
            "phase": "phase4_step28",
            "state": readiness.get("canonical_state"),
            "score": readiness.get("canonical_score"),
            "bounded": True,
        },
        "runtime_launch_visibility": {
            "phase": "phase4_step28",
            "startup_in_progress": not truly_ready,
            "calm_messaging": True,
            "bounded": True,
        },
        "runtime_launch_integrity": {
            "phase": "phase4_step28",
            "api_reachable": api_ok,
            "mission_control_reachable": mc_ok,
            "coordination_complete": truly_ready,
            "bounded": True,
        },
    }
