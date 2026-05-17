# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise runtime governance coordinator (Phase 4 Step 26)."""

from __future__ import annotations

from typing import Any

from app.services.runtime.enterprise_runtime_integrity_final import build_enterprise_runtime_integrity_final
from app.services.runtime.runtime_ownership_authority import build_runtime_ownership_authority
from app.services.runtime.runtime_recovery_authority import build_runtime_recovery_authority
from app.services.runtime.runtime_truth_ownership_lock import build_runtime_truth_authority


def build_runtime_governance_authority(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    ownership = build_runtime_ownership_authority(truth)
    recovery = build_runtime_recovery_authority(truth)
    truth_auth = build_runtime_truth_authority(truth)
    integrity = build_enterprise_runtime_integrity_final(truth)
    own = ownership.get("runtime_ownership_authority") or {}
    rec = recovery.get("runtime_recovery_authority") or {}
    final = integrity.get("enterprise_runtime_integrity_final") or {}
    governed = bool(own.get("authoritative") and rec.get("authoritative") and final.get("enterprise_runtime_integrity_verified"))
    return {
        "runtime_governance_authority": {
            "phase": "phase4_step26",
            "authoritative": governed,
            "domains": [
                "runtime_integrity",
                "recovery_integrity",
                "startup_integrity",
                "hydration_integrity",
                "process_supervision",
                "operational_continuity",
                "runtime_authority",
                "enterprise_readiness",
                "runtime_trust",
                "operational_calmness",
            ],
            "message": (
                "Enterprise runtime governance is authoritative."
                if governed
                else "Runtime governance is coordinating stabilization — advisory recovery remains available."
            ),
            "bounded": True,
        },
        "runtime_governance_integrity": {
            "phase": "phase4_step26",
            "integrity_ok": bool(final.get("enterprise_runtime_integrity_verified")),
            "ownership_authoritative": bool(own.get("authoritative")),
            "recovery_authoritative": bool(rec.get("authoritative")),
            "truth_authoritative": bool((truth_auth.get("runtime_truth_authority") or {}).get("runtime_truth_authoritative")),
            "bounded": True,
        },
        "runtime_governance_visibility": {
            "phase": "phase4_step26",
            "explainable": True,
            "advisory_first": True,
            "no_hidden_automation": True,
            "bounded": True,
        },
        "runtime_governance_discipline": {
            "phase": "phase4_step26",
            "orchestrator_owned": True,
            "bounded_persistence": True,
            "operator_authority_preserved": True,
            "bounded": True,
        },
        "enterprise_runtime_governance": {
            "phase": "phase4_step26",
            "governed": governed,
            "enterprise_runtime_governed": governed,
            "bounded": True,
        },
    }
