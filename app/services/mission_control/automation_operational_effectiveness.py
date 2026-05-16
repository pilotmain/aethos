# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Automation pack operational effectiveness (Phase 4 Step 1)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.automation_governance import build_automation_governance


def build_automation_operational_effectiveness(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    gov = build_automation_governance(truth)
    packs = (truth or {}).get("automation_packs") or []
    n = len(packs) if isinstance(packs, list) else int(gov.get("pack_count") or 0)
    failures = int(gov.get("failure_count") or 0)
    success_rate = max(0.0, 1.0 - failures / max(1, n))
    return {
        "pack_count": n,
        "success_rate": round(success_rate, 3),
        "operator_approved": True,
        "governance_visible": True,
        "sequencing_supported": True,
        "dependency_aware": True,
    }


def build_automation_execution_quality(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    eff = build_automation_operational_effectiveness(truth)
    return {
        "quality_score": eff.get("success_rate"),
        "execution_scope": "operator_triggered",
        "provider_aware": True,
        "runtime_aware": True,
        "escalation_aware": True,
    }


def build_automation_reliability(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    eff = build_automation_operational_effectiveness(truth)
    return {"reliability_score": eff.get("success_rate"), "bounded": True}


def build_automation_adaptation(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "adaptation_mode": "advisory",
        "effectiveness": build_automation_operational_effectiveness(truth),
        "execution_quality": build_automation_execution_quality(truth),
        "reliability": build_automation_reliability(truth),
    }
