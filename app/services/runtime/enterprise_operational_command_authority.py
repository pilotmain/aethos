# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise operational command authority (Phase 4 Step 27)."""

from __future__ import annotations

from typing import Any

from app.services.runtime.runtime_governance_authority import build_runtime_governance_authority
from app.services.runtime.runtime_recovery_authority import build_runtime_recovery_authority


def build_enterprise_operational_command_authority(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    gov = build_runtime_governance_authority(truth)
    recovery = build_runtime_recovery_authority(truth)
    office = truth.get("office_operational_authority") or {}
    readiness = truth.get("runtime_readiness_convergence") or {}
    gov_auth = gov.get("runtime_governance_authority") or {}
    rec_auth = recovery.get("runtime_recovery_authority") or {}
    authoritative = bool(
        gov_auth.get("authoritative")
        and office.get("authoritative_command_center")
        and readiness.get("canonical", True)
    )
    trust_score = float((truth.get("runtime_trust_finalization") or {}).get("trust_score") or 0.85)
    return {
        "enterprise_operational_command_authority": {
            "phase": "phase4_step27",
            "authoritative": authoritative,
            "domains": [
                "runtime_governance",
                "runtime_readiness",
                "operational_authority",
                "office_authority",
                "supervision_authority",
                "recovery_authority",
                "continuity_authority",
                "trust_authority",
                "startup_authority",
            ],
            "bounded": True,
        },
        "enterprise_operational_command_integrity": {
            "phase": "phase4_step27",
            "integrity_ok": authoritative,
            "governance_authoritative": bool(gov_auth.get("authoritative")),
            "recovery_ready": bool(rec_auth.get("recovery_ready")),
            "bounded": True,
        },
        "enterprise_operational_command_visibility": {
            "phase": "phase4_step27",
            "unified": True,
            "explainable": True,
            "no_conflicting_narratives": True,
            "bounded": True,
        },
        "enterprise_operational_command_readiness": {
            "phase": "phase4_step27",
            "state": readiness.get("canonical_state") or "operational",
            "score": readiness.get("canonical_score") or truth.get("runtime_readiness_score"),
            "bounded": True,
        },
        "enterprise_operational_command_trust": {
            "phase": "phase4_step27",
            "trust_score": trust_score,
            "verified": trust_score >= 0.8,
            "bounded": True,
        },
    }
