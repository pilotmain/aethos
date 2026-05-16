# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""AethOS-native differentiation summary — runtime-backed (Phase 3 Step 2)."""

from __future__ import annotations

from typing import Any

from app.marketplace.runtime_marketplace import marketplace_summary
from app.plugins.automation_packs import list_automation_packs_with_health
from app.services.brain_routing_visibility import build_brain_routing_panel
from app.services.operational_intelligence import build_operational_intelligence
from app.services.privacy_operational_posture import build_privacy_operational_posture
from app.services.provider_intelligence_panel import build_provider_intelligence_panel
from app.services.runtime_governance import build_governance_audit


def build_differentiators_summary(*, ort: dict[str, Any] | None = None) -> dict[str, Any]:
    """Single payload for why AethOS differs from OpenClaw — all runtime-backed."""
    ort = ort or {}
    return {
        "advantages": [
            "privacy_aware_autonomous_operations",
            "brain_agnostic_intelligence_routing",
            "built_in_mission_control",
            "provider_project_intelligence",
            "runtime_governance",
            "installable_automation_packs",
            "bounded_operational_intelligence",
            "lightweight_runtime_philosophy",
        ],
        "privacy_posture": build_privacy_operational_posture(),
        "brain_routing": build_brain_routing_panel(),
        "provider_intelligence": build_provider_intelligence_panel(),
        "operational_intelligence": build_operational_intelligence(ort),
        "governance": build_governance_audit(),
        "automation_packs": list_automation_packs_with_health(),
        "marketplace_health": marketplace_summary(),
        "openclaw_parity": "maintained",
        "differentiation_version": "phase3_step2",
    }


def build_differentiation_panels(*, ort: dict[str, Any] | None = None) -> dict[str, Any]:
    summary = build_differentiators_summary(ort=ort)
    return {
        "privacy_posture": summary.get("privacy_posture"),
        "brain_routing": summary.get("brain_routing"),
        "provider_intelligence": summary.get("provider_intelligence"),
        "operational_intelligence": summary.get("operational_intelligence"),
        "governance_audit": summary.get("governance"),
        "automation_packs": summary.get("automation_packs"),
        "marketplace_health": summary.get("marketplace_health"),
    }
