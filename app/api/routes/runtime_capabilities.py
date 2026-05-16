# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Top-level runtime APIs — capabilities and performance (Phase 4 Step 6–7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.security import get_valid_web_user_id
from app.services.mission_control.runtime_api_capabilities import build_runtime_capabilities
from app.services.mission_control.runtime_async_hydration import build_hydration_status
from app.services.mission_control.runtime_operational_throttling import (
    build_responsiveness_score,
    build_runtime_operational_throttling,
)
from app.services.mission_control.runtime_payload_profiles import (
    PROFILES,
    apply_payload_profile,
    build_payload_profile_metrics,
)
from app.services.mission_control.runtime_performance_intelligence import (
    build_runtime_performance_intelligence,
)
from app.services.mission_control.worker_memory_archive import build_worker_archive_visibility

router = APIRouter(prefix="/runtime", tags=["runtime"])


def _truth_slice(app_user_id: str) -> dict:
    from app.services.mission_control.runtime_truth import build_runtime_truth
    from app.services.mission_control.runtime_truth_cache import get_cached_runtime_truth

    return get_cached_runtime_truth(app_user_id, lambda uid: build_runtime_truth(user_id=uid))


@router.get("/capabilities")
def runtime_capabilities(_: str = Depends(get_valid_web_user_id)) -> dict:
    return build_runtime_capabilities()


@router.get("/performance")
def runtime_performance(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    t = _truth_slice(app_user_id)
    return build_runtime_performance_intelligence(t)


@router.get("/hydration")
def runtime_hydration(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    t = _truth_slice(app_user_id)
    return build_hydration_status(t)


@router.get("/payloads")
def runtime_payloads(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    t = _truth_slice(app_user_id)
    return build_payload_profile_metrics(t)


@router.get("/throttling")
def runtime_throttling(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    t = _truth_slice(app_user_id)
    return build_runtime_operational_throttling(t)


@router.get("/responsiveness")
def runtime_responsiveness(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    t = _truth_slice(app_user_id)
    return build_responsiveness_score(t)


@router.get("/profile/{profile_name}")
def runtime_profile(
    profile_name: str,
    max_tier: str = Query("operational"),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.services.mission_control.runtime_async_hydration import hydrate_progressive_truth

    name = profile_name.strip().lower()
    if name not in PROFILES:
        return {"error": "unknown_profile", "available": sorted(PROFILES)}
    truth = hydrate_progressive_truth(user_id=app_user_id, max_tier=max_tier)
    return apply_payload_profile(truth, name)


@router.get("/partitions")
def runtime_partitions(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_operational_partitions import build_runtime_operational_partitions

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_operational_partitions(t)


@router.get("/eras")
def runtime_eras(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_long_horizon import build_runtime_long_horizon

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_long_horizon(t)


@router.get("/production-posture")
def runtime_production_posture(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_production_posture import build_production_runtime_posture

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_production_runtime_posture(t)


@router.get("/summaries")
def runtime_summaries(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_enterprise_summarization import build_enterprise_runtime_summaries

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_enterprise_runtime_summaries(t)


@router.get("/calmness-lock")
def runtime_calmness_lock(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_calmness_integrity import build_runtime_calmness_integrity

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_calmness_integrity(t)
