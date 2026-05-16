# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Unified runtime operator experience bundle (Phase 4 Step 12)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.enterprise_operator_trust import build_enterprise_operator_trust
from app.services.mission_control.mission_control_language_system import build_mission_control_language_system
from app.services.mission_control.runtime_perception_responsiveness import build_runtime_perception_responsiveness
from app.services.mission_control.runtime_routing_visibility import (
    build_provider_health_matrix,
    build_routing_explanations,
    build_routing_history,
)


def build_runtime_operator_experience(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "runtime_operator_experience": {
            "cohesive": True,
            "summary_first": True,
            "enterprise_calm": True,
        },
        "runtime_perception": build_runtime_perception_responsiveness(truth),
        "routing_visibility": {
            "history": build_routing_history(truth),
            "explanations": build_routing_explanations(truth),
            "provider_health_matrix": build_provider_health_matrix(truth),
        },
        "operator_trust": build_enterprise_operator_trust(truth),
        "unified_language": build_mission_control_language_system(),
        "marketplace_clarity": _marketplace_clarity(),
    }


def _marketplace_clarity() -> dict[str, str]:
    return {
        "runtime_plugin": "Extends runtime and provider capabilities",
        "automation_pack": "Operator-triggered operational workflow pack",
        "marketplace_skill": "Installable AI execution capability package",
    }
