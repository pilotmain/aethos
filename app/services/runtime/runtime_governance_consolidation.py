# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Final governance convergence (Phase 4 Step 27)."""

from __future__ import annotations

from typing import Any

from app.services.runtime.enterprise_operational_command_authority import build_enterprise_operational_command_authority
from app.services.runtime.runtime_governance_authority import build_runtime_governance_authority
from app.services.runtime.runtime_truth_governance_lock import build_runtime_truth_governance_lock


def build_runtime_governance_consolidation(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    gov = build_runtime_governance_authority(truth)
    cmd = build_enterprise_operational_command_authority(truth)
    truth_lock = build_runtime_truth_governance_lock(truth)
    converged = bool(
        (gov.get("runtime_governance_authority") or {}).get("authoritative")
        and (cmd.get("enterprise_operational_command_authority") or {}).get("authoritative")
        and truth_lock.get("runtime_truth_governed")
    )
    return {
        "runtime_governance_consolidation": {
            "phase": "phase4_step27",
            "converged": converged,
            "consolidated_domains": [
                "governance_authority",
                "operational_authority",
                "truth_authority",
                "startup_authority",
                "supervision_authority",
                "continuity_authority",
                "trust_authority",
            ],
            "bounded": True,
        },
        "enterprise_runtime_governance_final": {
            "phase": "phase4_step27",
            "finalized": converged,
            "bounded": True,
        },
        "runtime_operational_governance_final": {
            "phase": "phase4_step27",
            "authoritative": converged,
            "bounded": True,
        },
    }
