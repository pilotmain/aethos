# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 6 — runtime stabilization and operational recovery."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_api_capabilities import build_runtime_capabilities
from app.services.mission_control.runtime_recovery_center import build_runtime_recovery_center
from app.services.mission_control.runtime_resilience import build_runtime_resilience_block
from app.services.mission_control.runtime_truth_integrity import validate_truth_integrity


def apply_runtime_evolution_step6_to_truth(truth: dict[str, Any]) -> dict[str, Any]:
    integrity = validate_truth_integrity(truth)
    truth["runtime_truth_integrity"] = integrity
    truth["truth_integrity_score"] = integrity.get("truth_integrity_score")

    resilience = truth.get("runtime_resilience")
    if not isinstance(resilience, dict) or not resilience.get("status"):
        truth["runtime_resilience"] = build_runtime_resilience_block(
            status="healthy" if integrity.get("cohesive") else "degraded"
        )

    center = build_runtime_recovery_center(truth)
    truth["runtime_recovery_center"] = center
    truth["operational_recovery_visibility"] = center

    truth["runtime_api_capabilities"] = build_runtime_capabilities()
    truth["phase4_step6"] = True
    return truth
