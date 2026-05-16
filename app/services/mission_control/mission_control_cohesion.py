# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control product cohesion checks (Phase 3 Step 3)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_truth import build_runtime_panels_from_truth


_REQUIRED_TRUTH_KEYS = frozenset(
    {
        "runtime_health",
        "runtime_agents",
        "office",
        "routing_summary",
        "privacy_posture",
        "plugins",
        "runtime_governance",
        "operational_intelligence",
        "brain_routing_panel",
        "marketplace",
        "differentiators",
        "runtime_discipline",
        "readable_summaries",
        "runtime_workers",
        "runtime_confidence",
    }
)

_REQUIRED_PANEL_KEYS = frozenset(
    {
        "runtime_health",
        "brain_routing",
        "provider_operations",
        "privacy_posture",
        "office_operational",
        "runtime_discipline",
    }
)


def build_cohesion_report(truth: dict[str, Any]) -> dict[str, Any]:
    missing_truth = sorted(_REQUIRED_TRUTH_KEYS - set(truth.keys()))
    panels = build_runtime_panels_from_truth(truth)
    missing_panels = sorted(_REQUIRED_PANEL_KEYS - set(panels.keys()))
    office = truth.get("office") or {}
    return {
        "cohesive": not missing_truth and not missing_panels,
        "missing_truth_keys": missing_truth,
        "missing_panel_keys": missing_panels,
        "office_has_orchestrator": bool(office.get("orchestrator")),
        "single_truth_path": True,
    }
