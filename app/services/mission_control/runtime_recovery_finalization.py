# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Recovery discipline metrics (Phase 4 Step 20)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state
from app.services.mission_control.runtime_restart_manager import build_runtime_restarts


def build_runtime_recovery_finalization(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    st = load_runtime_state()
    restarts = build_runtime_restarts(truth)
    history = list(restarts.get("restart_history") or [])
    ok_count = sum(1 for r in history if r.get("ok"))
    sup = truth.get("runtime_process_supervision") or {}
    conflicts = list(sup.get("conflicts") or [])
    return {
        "runtime_recovery_finalization": {
            "recovery_success_rate": round(ok_count / max(1, len(history)), 3) if history else 1.0,
            "startup_recovery_rate": 1.0 if truth.get("runtime_supervision_verified") else 0.85,
            "lock_conflict_frequency": len(conflicts),
            "supervision_conflict_rate": min(1.0, len(conflicts) / 3.0),
            "hydration_recovery_rate": 1.0 - float((truth.get("hydration_progress") or {}).get("partial") or 0),
            "recovery_narratives": {
                "startup": "AethOS runtime is recovering startup ownership…",
                "partial_mc": "Mission Control is operating in partial readiness while runtime intelligence hydrates.",
            },
            "lifecycle_events": (st.get("recovery") or {}).get("events", [])[-8:],
            "bounded": True,
        }
    }
