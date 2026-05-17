# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Final calm degraded-mode behavior (Phase 4 Step 24)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_operational_authority import build_runtime_operational_authority


def build_runtime_degraded_mode_finalization(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    authority = build_runtime_operational_authority(truth)
    partial = authority["operational_authority"].get("hydration_partial", False)
    degraded = authority["operational_authority"].get("degraded_mode", False)
    if partial:
        headline = (
            "Enterprise intelligence is still synchronizing. Core orchestration remains operational."
        )
    elif degraded:
        headline = (
            "AethOS temporarily reduced advanced runtime analysis while maintaining operational continuity."
        )
    else:
        headline = "AethOS runtime is operating in full enterprise mode."
    return {
        "runtime_degraded_mode_finalization": {
            "degraded": degraded or partial,
            "operational": True,
            "calm": True,
            "useful": True,
            "explainable": True,
            "office_continuity_preserved": True,
            "operator_headline": headline,
            "phase": "phase4_step24",
            "bounded": True,
        }
    }
