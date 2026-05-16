# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise operational trust panels (Phase 3 Step 14)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.automation_governance import build_automation_governance, build_automation_trust
from app.services.mission_control.execution_visibility import build_execution_visibility
from app.services.mission_control.operational_explainability import build_operational_explainability
from app.services.mission_control.operational_trust import build_operational_trust_model
from app.services.mission_control.provider_governance_visibility import build_provider_governance, build_provider_trust
from app.services.mission_control.runtime_escalations import build_escalation_visibility
from app.services.mission_control.worker_accountability import (
    build_worker_accountability,
    build_worker_governance,
    build_worker_operational_quality,
)


def build_enterprise_trust_panels(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "governance_trust": build_operational_trust_model(truth).get("governance_integrity"),
        "runtime_accountability": build_operational_trust_model(truth).get("runtime_accountability"),
        "provider_trust": build_provider_trust(truth),
        "provider_governance": build_provider_governance(truth),
        "automation_trust": build_automation_trust(truth),
        "automation_governance": build_automation_governance(truth),
        "worker_trust": build_operational_trust_model(truth).get("worker_trust"),
        "worker_accountability": build_worker_accountability(truth),
        "worker_governance": build_worker_governance(truth),
        "worker_operational_quality": build_worker_operational_quality(truth),
        "operational_explainability": build_operational_explainability(truth),
        "execution_visibility": build_execution_visibility(truth),
        "escalation_health": build_escalation_visibility(truth),
        "operational_trust_score": build_operational_trust_model(truth).get("operational_trust_score"),
    }
