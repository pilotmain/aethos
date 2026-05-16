# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 8 — production runtime convergence."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.governance_operational_index import build_governance_operational_index
from app.services.mission_control.runtime_calmness_integrity import build_runtime_calmness_integrity
from app.services.mission_control.runtime_enterprise_summarization import build_enterprise_runtime_summaries
from app.services.mission_control.runtime_long_horizon import build_runtime_long_horizon
from app.services.mission_control.runtime_operational_partitions import build_runtime_operational_partitions
from app.services.mission_control.runtime_production_posture import build_production_runtime_posture
from app.services.mission_control.worker_operational_lifecycle import build_worker_operational_lifecycle


def apply_runtime_evolution_step8_to_truth(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    truth["runtime_long_horizon"] = build_runtime_long_horizon(truth)
    truth["operational_eras"] = truth["runtime_long_horizon"].get("operational_eras")
    truth["runtime_history_windows"] = truth["runtime_long_horizon"].get("runtime_history_windows")
    truth["governance_eras"] = truth["runtime_long_horizon"].get("governance_eras")
    truth["enterprise_memory_timeline"] = truth["runtime_long_horizon"].get("enterprise_memory_timeline")

    summaries = build_enterprise_runtime_summaries(truth)
    truth["enterprise_runtime_summaries"] = summaries
    truth.update(summaries)

    truth["runtime_operational_partitions"] = build_runtime_operational_partitions(truth)
    truth["governance_operational_index"] = build_governance_operational_index(truth)

    calm = build_runtime_calmness_integrity(truth)
    truth["runtime_calmness_integrity"] = calm
    truth["calmness_integrity"] = calm.get("calmness_integrity")
    truth["operational_noise_score"] = calm.get("operational_noise_score")
    truth["escalation_visibility_score"] = calm.get("escalation_visibility_score")

    lifecycle = build_worker_operational_lifecycle(truth)
    truth["worker_operational_lifecycle"] = lifecycle
    truth["worker_lifecycle_maturity"] = lifecycle.get("worker_lifecycle_maturity")

    posture = build_production_runtime_posture(truth)
    truth.update(posture)
    truth["phase4_step8"] = True
    return truth
