# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 22 — runtime integrity and operational authority lock."""

from __future__ import annotations

from typing import Any


def apply_runtime_evolution_step22_to_truth(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    from app.services.mission_control.operator_confidence_engine import build_operator_confidence
    from app.services.mission_control.runtime_cold_start_reliability import build_runtime_cold_start_reliability
    from app.services.mission_control.runtime_integrity_certification import (
        build_enterprise_runtime_integrity,
        build_runtime_integrity_certification,
    )
    from app.services.mission_control.runtime_operational_authority import build_runtime_operational_authority
    from app.services.mission_control.runtime_readiness_authority import build_runtime_readiness_authority
    from app.services.mission_control.runtime_recovery_integrity import (
        build_runtime_recovery_history,
        build_runtime_recovery_integrity,
    )
    from app.services.mission_control.runtime_status_unification import build_runtime_status_unification
    from app.services.mission_control.runtime_surface_consolidation import build_runtime_surface_consolidation
    from app.services.mission_control.runtime_truth_consistency import (
        build_runtime_truth_consistency,
        build_runtime_truth_integrity,
    )
    from app.services.mission_control.runtime_truth_schema_lock import build_runtime_truth_schema_lock

    truth.update(build_runtime_readiness_authority(truth))
    truth.update(build_runtime_operational_authority(truth))
    truth.update(build_runtime_status_unification(truth))
    truth.update(build_runtime_cold_start_reliability(truth))
    truth.update(build_runtime_recovery_integrity(truth))
    truth.update(build_runtime_recovery_history(truth))
    truth.update(build_runtime_integrity_certification(truth))
    truth.update(build_enterprise_runtime_integrity(truth))
    truth.update(build_operator_confidence(truth))
    truth.update(build_runtime_truth_schema_lock(truth))
    truth.update(build_runtime_truth_integrity(truth))
    truth.update(build_runtime_truth_consistency(truth))
    truth.update(build_runtime_surface_consolidation())
    cert = truth.get("runtime_integrity_certification") or {}
    truth["phase4_step22"] = True
    truth["runtime_integrity_locked"] = bool(cert.get("production_ready"))
    truth["enterprise_runtime_assurance"] = cert.get("enterprise_grade")
    return truth
