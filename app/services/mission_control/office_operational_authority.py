# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Office operational authority — authoritative command center (Phase 4 Step 24)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.office_operational_stream import build_office_operational_stream
from app.services.mission_control.operator_confidence_engine import build_operator_confidence


def build_office_operational_authority(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    stream = build_office_operational_stream(truth)
    confidence = build_operator_confidence(truth)
    partial = bool((truth.get("hydration_progress") or {}).get("partial"))
    unlocked = list((truth.get("runtime_startup_experience") or {}).get("progressive_surface_unlock") or ["office"])
    narrative = (truth.get("runtime_unified_narrative_engine") or {}).get("headline")
    readiness = truth.get("runtime_readiness_convergence") or {}
    return {
        "office_operational_authority": {
            "authoritative_command_center": True,
            "single_operational_command_surface": True,
            "never_noisy": True,
            "no_conflicting_states": True,
            "no_stacked_banners": True,
            "unified_narrative": narrative,
            "readiness_state": readiness.get("canonical_state"),
            "progressive_panel_unlock": unlocked,
            "graceful_degradation": partial,
            "priority_work_visible": True,
            "coordinates": [
                "readiness",
                "startup",
                "degraded_mode",
                "recovery",
                "governance",
                "operational_pressure",
                "runtime_trust",
                "operational_continuity",
            ],
            "bounded": True,
        },
        "office_operational_focus": {
            "primary": "orchestrator_and_workers",
            "preserve_operator_focus": True,
            "bounded": True,
        },
        "office_operational_readiness": {
            "ready": not partial or "office" in unlocked,
            "confidence_summary": confidence["operator_confidence"]["summary"],
            "primary_entrypoint": True,
            "summarizes": ["readiness", "routing", "governance", "runtime_trust", "continuity", "operational_state"],
            "bounded": True,
        },
        "office_operational_priority_stream": stream,
        "phase": "phase4_step28",
        "bounded": True,
    }
