# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 13 — launch readiness and final convergence."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.enterprise_calmness_metrics import (
    build_runtime_calmness_metrics,
    build_runtime_signal_health,
)
from app.services.mission_control.final_legacy_policy import build_final_legacy_policy
from app.services.mission_control.launch_identity_lock import build_aethos_launch_identity
from app.services.mission_control.launch_readiness_certification import build_launch_readiness_certification
from app.services.mission_control.operational_storytelling_final import build_operational_storytelling_final
from app.services.mission_control.runtime_duplication_lock import build_runtime_duplication_lock
from app.services.mission_control.runtime_launch_focus import build_runtime_operational_focus_launch
from app.services.mission_control.runtime_recovery_experience import build_runtime_recovery_experience


def apply_runtime_evolution_step13_to_truth(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    truth.update(build_runtime_duplication_lock(truth))
    truth.update(build_runtime_operational_focus_launch(truth))
    truth.update(build_runtime_recovery_experience(truth, user_id=user_id))
    truth.update(build_operational_storytelling_final(truth))
    truth.update(build_aethos_launch_identity(truth))
    truth["launch_readiness_certification"] = build_launch_readiness_certification()
    truth["runtime_calmness_metrics"] = build_runtime_calmness_metrics(truth)
    truth["runtime_signal_health"] = build_runtime_signal_health(truth)
    truth["final_legacy_policy"] = build_final_legacy_policy()
    truth["phase4_step13"] = True
    truth["launch_ready"] = True
    return truth
