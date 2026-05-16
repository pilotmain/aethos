# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 9 — enterprise operational surfaces and MC experience."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.enterprise_operational_overview import build_executive_operational_overview
from app.services.mission_control.governance_experience_layer import build_governance_experience_layer
from app.services.mission_control.governance_timeline_experience import build_governance_timeline_experience
from app.services.mission_control.mission_control_language_system import build_mission_control_language_system
from app.services.mission_control.operational_narrative_engine import build_operational_narratives_v2
from app.services.mission_control.runtime_explainability_center import build_runtime_explainability_center
from app.services.mission_control.worker_ecosystem_experience import build_worker_ecosystem_experience


def apply_runtime_evolution_step9_to_truth(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    gov = build_governance_experience_layer(truth)
    truth.update(gov)

    worker = build_worker_ecosystem_experience(truth)
    truth.update(worker)

    exec_over = build_executive_operational_overview(truth)
    truth.update(exec_over)

    narratives = build_operational_narratives_v2(truth)
    truth.update(narratives)

    timeline = build_governance_timeline_experience(truth)
    truth.update(timeline)

    truth["mission_control_language_system"] = build_mission_control_language_system()

    explain = build_runtime_explainability_center(truth)
    truth.update(explain)

    truth["phase4_step9"] = True
    return truth
