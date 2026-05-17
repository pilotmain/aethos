# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 26 — enterprise runtime governance and autonomy lock."""

from __future__ import annotations

from typing import Any


def apply_runtime_evolution_step26_to_truth(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    from app.services.mission_control.enterprise_calmness_metrics import build_runtime_calmness_metrics
    from app.services.mission_control.runtime_calmness_lock import build_runtime_calmness_lock
    from app.services.runtime.enterprise_runtime_final_certification import build_enterprise_runtime_final_certification
    from app.services.runtime.runtime_autonomous_coordination import build_runtime_autonomous_coordination
    from app.services.runtime.runtime_enterprise_safety_lock import build_runtime_enterprise_safety_lock
    from app.services.runtime.runtime_governance_authority import build_runtime_governance_authority
    from app.services.runtime.runtime_operational_governance_timeline import build_runtime_operational_governance_timeline
    from app.services.runtime.runtime_pressure_governance import build_runtime_pressure_governance
    from app.services.runtime.runtime_trust_finalization import build_runtime_trust_finalization
    from app.services.runtime.runtime_truth_governance_lock import build_runtime_truth_governance_lock

    truth.update(build_runtime_governance_authority(truth))
    truth.update(build_runtime_autonomous_coordination(truth))
    truth.update(build_runtime_operational_governance_timeline(truth))
    truth.update(build_runtime_pressure_governance(truth))
    truth.update(build_runtime_enterprise_safety_lock(truth))
    truth.update(build_runtime_trust_finalization(truth))
    truth.update(build_runtime_truth_governance_lock(truth))
    truth.update(build_runtime_calmness_lock(truth))
    truth["runtime_calmness_metrics"] = build_runtime_calmness_metrics(truth)
    truth.update(build_enterprise_runtime_final_certification(truth))
    final = truth.get("enterprise_runtime_final_certification") or {}
    truth["phase4_step26"] = True
    truth["enterprise_runtime_governed"] = bool(final.get("enterprise_runtime_governed"))
    truth["enterprise_runtime_fully_certified"] = bool(final.get("enterprise_runtime_fully_certified"))
    truth["enterprise_runtime_trusted"] = bool(final.get("enterprise_runtime_trusted"))
    truth["production_runtime_finalized"] = bool(final.get("production_runtime_finalized"))
    truth["runtime_governance_locked"] = bool(truth.get("runtime_governance_locked"))
    return truth
