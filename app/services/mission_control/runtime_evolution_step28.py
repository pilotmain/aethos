# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 28 — enterprise setup and launch finalization."""

from __future__ import annotations

from typing import Any


def apply_runtime_evolution_step28_to_truth(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    from app.services.mission_control.office_operational_authority import build_office_operational_authority
    from app.services.runtime.runtime_launch_experience import build_runtime_launch_experience
    from app.services.runtime.runtime_readiness_convergence import build_runtime_readiness_convergence
    from app.services.runtime.runtime_startup_orchestration import build_runtime_startup_orchestration
    from app.services.runtime.runtime_startup_visibility import build_runtime_startup_visibility
    from app.services.setup.setup_operational_recovery import build_setup_operational_recovery

    truth.update(build_runtime_readiness_convergence(truth))
    truth.update(build_runtime_launch_experience(truth))
    truth.update(build_runtime_startup_visibility(truth))
    truth.update(build_runtime_startup_orchestration(truth))
    truth["setup_operational_recovery"] = build_setup_operational_recovery()["setup_operational_recovery"]
    truth.update(build_office_operational_authority(truth))
    launch = truth.get("runtime_launch_experience") or {}
    truth["phase4_step28"] = True
    truth["enterprise_setup_finalized"] = bool(truth.get("setup_ready_state_locked"))
    truth["runtime_launch_finalized"] = bool(launch.get("truly_operational") or truth.get("enterprise_runtime_finalized"))
    truth["installer_interaction_locked"] = True
    return truth
