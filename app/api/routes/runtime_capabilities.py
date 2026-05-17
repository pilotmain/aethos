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
    from app.services.mission_control.runtime_calmness_lock import build_runtime_calmness_lock

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    out = build_runtime_calmness_integrity(t)
    out.update(build_runtime_calmness_lock(t))
    return out


@router.get("/routing")
def runtime_routing_visibility(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_provider_routing import build_runtime_provider_routing

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_provider_routing(t)


@router.get("/restarts")
def runtime_restarts(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_restart_manager import build_runtime_restarts

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_restarts(t)


@router.get("/identity")
def runtime_identity_state(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_identity_final import build_aethos_runtime_identity_final

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_aethos_runtime_identity_final(t)


@router.get("/routing/history")
def runtime_routing_history(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_routing_visibility import build_routing_history

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_routing_history(t)


@router.get("/routing/explanations")
def runtime_routing_explanations(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_routing_visibility import build_routing_explanations

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_routing_explanations(t)


@router.get("/providers/health-matrix")
def runtime_providers_health_matrix(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_routing_visibility import build_provider_health_matrix

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_provider_health_matrix(t)


@router.get("/perception")
def runtime_perception(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_perception_responsiveness import build_runtime_perception_responsiveness

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_perception_responsiveness(t)


@router.get("/operator-experience")
def runtime_operator_experience(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_operator_experience import build_runtime_operator_experience

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_operator_experience(t)


@router.get("/operational-focus")
def runtime_operational_focus(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_launch_focus import build_runtime_operational_focus_launch

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_operational_focus_launch(t)


@router.get("/priority-work")
def runtime_priority_work(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_launch_focus import build_runtime_priority_work

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_priority_work(t)


@router.get("/noise-reduction")
def runtime_noise_reduction(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_launch_focus import build_runtime_noise_reduction

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_noise_reduction(t)


@router.get("/calmness-metrics")
def runtime_calmness_metrics(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.enterprise_calmness_metrics import build_runtime_calmness_metrics

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_calmness_metrics(t)


@router.get("/signal-health")
def runtime_signal_health(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.enterprise_calmness_metrics import build_runtime_signal_health

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_signal_health(t)


@router.get("/launch-certification")
def runtime_launch_certification(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.launch_readiness_certification import build_launch_readiness_certification

    return build_launch_readiness_certification()


@router.get("/readiness-progress")
def runtime_readiness_progress(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_cold_start_lock import build_runtime_readiness_progress

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_readiness_progress(t)


@router.get("/cold-start")
def runtime_cold_start(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_cold_start_lock import build_runtime_cold_start

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_cold_start(t)


@router.get("/partial-availability")
def runtime_partial_availability(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_cold_start_lock import build_runtime_partial_availability

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_partial_availability(t)


@router.get("/release-candidate")
def runtime_release_candidate(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.release_candidate_certification import build_release_candidate_certification

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_release_candidate_certification(t)


@router.get("/certification")
def runtime_certification(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.release_candidate_certification import build_runtime_certification_bundle

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_certification_bundle(t)


@router.get("/enterprise-grade")
def runtime_enterprise_grade(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.release_candidate_certification import build_runtime_enterprise_grade

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_enterprise_grade(t)


@router.get("/startup")
def runtime_startup(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_startup_experience import build_runtime_startup_experience

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_startup_experience(t)


@router.get("/readiness")
def runtime_readiness(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_startup_experience import build_runtime_readiness

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_readiness(t)


@router.get("/hydration/stages")
def runtime_hydration_stages(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_startup_experience import build_runtime_hydration_stages

    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    return build_runtime_hydration_stages(t)


@router.get("/compatibility")
def runtime_compatibility(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_evolution_step16 import build_runtime_compatibility

    return build_runtime_compatibility()


@router.get("/bootstrap")
def runtime_bootstrap(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_bootstrap import build_runtime_bootstrap

    return build_runtime_bootstrap()


@router.get("/branding-audit")
def runtime_branding_audit(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_branding_audit import build_runtime_branding_audit

    return build_runtime_branding_audit()


@router.get("/ownership")
def runtime_ownership(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_ownership_lock import build_runtime_ownership_status

    return build_runtime_ownership_status()


@router.get("/services")
def runtime_services(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_service_registry import build_runtime_service_registry

    return build_runtime_service_registry()


@router.get("/processes")
def runtime_processes(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_service_registry import build_runtime_processes

    return build_runtime_processes()


@router.get("/db-health")
def runtime_db_health(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_db_coordination import build_runtime_db_health

    return build_runtime_db_health()


@router.get("/startup-lock")
def runtime_startup_lock(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_startup_coordination import build_startup_lock_status

    return build_startup_lock_status()


@router.get("/supervision")
def runtime_supervision(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_supervision import build_runtime_supervision

    return build_runtime_supervision()


@router.get("/hydration/diagnostics")
def runtime_hydration_diagnostics(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    from app.services.mission_control.runtime_hydration_diagnostics import build_runtime_hydration_diagnostics

    return build_runtime_hydration_diagnostics(t)


@router.get("/certify")
def runtime_certify(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    from app.services.setup.production_cut_certification import build_production_cut_certification

    return build_production_cut_certification(truth=t)


@router.get("/surface-map")
def runtime_surface_map(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_surface_consolidation import build_runtime_surface_consolidation

    return build_runtime_surface_consolidation()


@router.get("/branding-convergence")
def runtime_branding_convergence(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.setup.final_branding_convergence_audit import build_final_branding_convergence_audit

    return build_final_branding_convergence_audit()


@router.get("/simplification-lock")
def runtime_simplification_lock(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    from app.services.mission_control.runtime_simplification_lock import build_runtime_simplification_lock

    return build_runtime_simplification_lock(t)


@router.get("/narrative-unification")
def runtime_narrative_unification(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    from app.services.mission_control.runtime_narrative_unification import build_runtime_narrative_unification

    return build_runtime_narrative_unification(t)


@router.get("/provider-routing-ux")
def runtime_provider_routing_ux(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    try:
        t = _truth_slice(app_user_id)
    except Exception:
        t = {}
    from app.services.mission_control.provider_routing_ux import build_provider_routing_ux

    return build_provider_routing_ux(t)


def _truth_or_empty(app_user_id: str) -> dict:
    try:
        return _truth_slice(app_user_id)
    except Exception:
        return {}


@router.get("/status")
def runtime_status(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_status_unification import build_unified_runtime_status

    return build_unified_runtime_status(_truth_or_empty(app_user_id))


@router.get("/health-summary")
def runtime_health_summary(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_status_unification import build_runtime_health_summary

    return build_runtime_health_summary(_truth_or_empty(app_user_id))


@router.get("/readiness-authority")
def runtime_readiness_authority(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_readiness_authority import build_runtime_readiness_authority

    return build_runtime_readiness_authority(_truth_or_empty(app_user_id))


@router.get("/operational-authority")
def runtime_operational_authority(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_operational_authority import build_runtime_operational_authority

    return build_runtime_operational_authority(_truth_or_empty(app_user_id))


@router.get("/recovery-history")
def runtime_recovery_history_route(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_recovery_integrity import build_runtime_recovery_history

    return build_runtime_recovery_history(_truth_or_empty(app_user_id))


@router.get("/recovery-integrity")
def runtime_recovery_integrity_route(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_recovery_integrity import build_runtime_recovery_integrity

    return build_runtime_recovery_integrity(_truth_or_empty(app_user_id))


@router.get("/integrity-certification")
def runtime_integrity_certification_route(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_integrity_certification import build_runtime_integrity_certification

    return build_runtime_integrity_certification(_truth_or_empty(app_user_id))


@router.get("/enterprise-integrity")
def runtime_enterprise_integrity(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_integrity_certification import build_enterprise_runtime_integrity

    return build_enterprise_runtime_integrity(_truth_or_empty(app_user_id))


@router.get("/truth-integrity")
def runtime_truth_integrity_route(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_truth_consistency import build_runtime_truth_integrity

    return build_runtime_truth_integrity(_truth_or_empty(app_user_id))


@router.get("/truth-consistency")
def runtime_truth_consistency_route(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_truth_consistency import build_runtime_truth_consistency

    return build_runtime_truth_consistency(_truth_or_empty(app_user_id))


@router.get("/operator-confidence")
def runtime_operator_confidence(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.operator_confidence_engine import build_operator_confidence

    return build_operator_confidence(_truth_or_empty(app_user_id))


@router.get("/state-machine")
def runtime_state_machine(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_operational_state_machine import build_runtime_operational_state_machine

    return build_runtime_operational_state_machine(_truth_or_empty(app_user_id))


@router.get("/assurance")
def runtime_assurance(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_assurance_engine import build_runtime_assurance_engine

    return build_runtime_assurance_engine(_truth_or_empty(app_user_id))


@router.get("/continuity-certification")
def runtime_continuity_certification_route(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_continuity_certification import build_runtime_continuity_certification

    return build_runtime_continuity_certification(_truth_or_empty(app_user_id))


@router.get("/persistence-health")
def runtime_persistence_health(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_continuity_certification import build_runtime_persistence_health

    return build_runtime_persistence_health(_truth_or_empty(app_user_id))


@router.get("/explainability")
def runtime_explainability_final(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_explainability_finalization import build_runtime_explainability_finalization

    return build_runtime_explainability_finalization(_truth_or_empty(app_user_id))


@router.get("/production-certification")
def runtime_production_certification_route(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_production_certification import build_runtime_production_certification

    return build_runtime_production_certification(_truth_or_empty(app_user_id))


@router.get("/operator-trust")
def runtime_operator_trust_route(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_production_certification import build_runtime_operator_trust

    return build_runtime_operator_trust(_truth_or_empty(app_user_id))


@router.get("/enterprise-readiness")
def runtime_enterprise_readiness_route(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_production_certification import build_runtime_enterprise_readiness

    return build_runtime_enterprise_readiness(_truth_or_empty(app_user_id))


@router.get("/operational-story")
def runtime_operational_story(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_operational_story_engine import build_runtime_operational_story_engine

    return build_runtime_operational_story_engine(_truth_or_empty(app_user_id))


@router.get("/stability")
def runtime_stability_route(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_stability_coordinator import build_runtime_stability_coordinator

    return build_runtime_stability_coordinator(_truth_or_empty(app_user_id))


@router.get("/long-session")
def runtime_long_session(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_long_session_reliability import build_runtime_long_session_reliability

    return build_runtime_long_session_reliability(_truth_or_empty(app_user_id))


@router.get("/office-authority")
def runtime_office_authority(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.office_operational_authority import build_office_operational_authority

    return build_office_operational_authority(_truth_or_empty(app_user_id))


@router.get("/memory-discipline")
def runtime_memory_discipline(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_operational_memory_discipline import build_runtime_operational_memory_discipline

    return build_runtime_operational_memory_discipline(_truth_or_empty(app_user_id))


@router.get("/degraded-mode")
def runtime_degraded_mode(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_degraded_mode_finalization import build_runtime_degraded_mode_finalization

    return build_runtime_degraded_mode_finalization(_truth_or_empty(app_user_id))


@router.get("/continuity-confidence")
def runtime_continuity_confidence(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_operator_continuity_confidence import build_runtime_operator_continuity_confidence

    return build_runtime_operator_continuity_confidence(_truth_or_empty(app_user_id))


@router.get("/responsiveness")
def runtime_responsiveness_guarantees_route(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_responsiveness_guarantees import build_runtime_responsiveness_guarantees

    return build_runtime_responsiveness_guarantees(_truth_or_empty(app_user_id))


@router.get("/release-freeze")
def runtime_release_freeze(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_release_freeze_lock import build_runtime_release_freeze_lock

    return build_runtime_release_freeze_lock(_truth_or_empty(app_user_id))


@router.get("/enterprise-certification")
def runtime_enterprise_certification(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.enterprise_operational_certification_final import (
        build_enterprise_operational_certification_final,
    )

    return build_enterprise_operational_certification_final(_truth_or_empty(app_user_id))


@router.get("/operational-story-final")
def runtime_operational_story_final_route(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_operational_story_engine import build_runtime_operational_story_final

    return build_runtime_operational_story_final(_truth_or_empty(app_user_id))


