# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 4 Step 7 — runtime performance convergence."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.office_operational_stream import build_office_operational_stream
from app.services.mission_control.runtime_async_hydration import build_hydration_status
from app.services.mission_control.runtime_operational_throttling import (
    build_responsiveness_score,
    build_runtime_operational_throttling,
)
from app.services.mission_control.runtime_payload_profiles import build_payload_profile_metrics
from app.services.mission_control.runtime_performance_intelligence import (
    build_runtime_performance_intelligence,
)
from app.services.mission_control.runtime_slice_persistence import (
    persist_truth_slices,
    slice_persistence_health,
)
from app.services.mission_control.worker_memory_archive import (
    archive_expired_worker_memory,
    build_worker_archive_visibility,
)


def apply_runtime_evolution_step7_to_truth(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    truth["runtime_operational_throttling"] = build_runtime_operational_throttling(truth)
    truth["runtime_performance_intelligence"] = build_runtime_performance_intelligence(truth)
    truth["operational_responsiveness"] = build_responsiveness_score(truth)
    truth["runtime_payload_profiles"] = build_payload_profile_metrics(truth)
    truth["office_operational_stream"] = build_office_operational_stream(truth)
    truth["hydration_status"] = build_hydration_status(truth)
    truth["worker_memory_archive"] = build_worker_archive_visibility()
    archive_expired_worker_memory(truth, user_id=user_id)
    persist_truth_slices(truth, user_id=user_id)
    truth["slice_persistence_health"] = slice_persistence_health(user_id)
    truth["phase4_step7"] = True
    return truth
