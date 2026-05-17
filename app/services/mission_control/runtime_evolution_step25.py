# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 25 — runtime ownership finalization."""

from __future__ import annotations

from typing import Any


def apply_runtime_evolution_step25_to_truth(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    from app.services.runtime.enterprise_runtime_integrity_final import build_enterprise_runtime_integrity_final
    from app.services.runtime.runtime_ownership_authority import build_runtime_ownership_authority
    from app.services.runtime.runtime_process_group_manager import build_process_group_status
    from app.services.runtime.runtime_recovery_authority import build_runtime_recovery_authority
    from app.services.runtime.runtime_truth_ownership_lock import build_runtime_truth_authority
    from app.services.mission_control.runtime_startup_coordination import build_runtime_startup_integrity
    from app.services.mission_control.runtime_supervision import build_runtime_supervision

    truth.update(build_runtime_ownership_authority(truth))
    truth.update(build_process_group_status())
    truth.update(build_runtime_recovery_authority(truth))
    truth.update(build_runtime_truth_authority(truth))
    truth.update(build_runtime_startup_integrity(truth))
    truth.update(build_enterprise_runtime_integrity_final(truth))
    sup = build_runtime_supervision()
    truth["runtime_supervision_live"] = sup.get("runtime_supervision")
    final = truth.get("enterprise_runtime_integrity_final") or {}
    truth["phase4_step25"] = True
    truth["runtime_ownership_authoritative"] = bool(
        (truth.get("runtime_ownership_authority") or {}).get("authoritative")
    )
    truth["runtime_supervision_verified"] = bool(final.get("process_supervision_verified"))
    truth["enterprise_runtime_consolidated"] = bool(final.get("enterprise_runtime_integrity_verified"))
    truth["process_supervision_locked"] = True
    truth["runtime_coordination_authoritative"] = bool(final.get("runtime_coordination_authoritative"))
    truth["production_runtime_locked"] = bool(final.get("production_runtime_locked"))
    return truth
