# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Formal runtime integrity certification (Phase 4 Step 22)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_cold_start_reliability import build_runtime_cold_start_reliability
from app.services.mission_control.runtime_operational_authority import build_runtime_operational_authority
from app.services.mission_control.runtime_readiness_authority import build_runtime_readiness_authority
from app.services.mission_control.runtime_recovery_integrity import build_runtime_recovery_integrity
from app.services.mission_control.runtime_truth_schema_lock import validate_runtime_truth_schema


INTEGRITY_CATEGORIES = (
    "hydration_integrity",
    "runtime_integrity",
    "surface_integrity",
    "provider_integrity",
    "governance_integrity",
    "worker_integrity",
    "recovery_integrity",
    "calmness_integrity",
    "branding_integrity",
    "setup_integrity",
)


def build_runtime_integrity_certification(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    readiness = build_runtime_readiness_authority(truth)["runtime_readiness_authority"]
    authority = build_runtime_operational_authority(truth)
    recovery = build_runtime_recovery_integrity(truth)["runtime_recovery_integrity"]
    cold = build_runtime_cold_start_reliability(truth)["cold_start_reliability"]
    schema = validate_runtime_truth_schema(truth)["runtime_truth_schema_lock"]
    blocking: list[str] = []
    scores: dict[str, float] = {
        "hydration_integrity": 0.9 if not cold.get("stalled_stage_detected") else 0.5,
        "runtime_integrity": readiness.get("score") or 0.0,
        "surface_integrity": 1.0 if authority["operational_authority"].get("authoritative") else 0.75,
        "provider_integrity": 0.85,
        "governance_integrity": float((truth.get("governance_readiness") or {}).get("score") or 0.8),
        "worker_integrity": float((truth.get("worker_ecosystem_health") or {}).get("score") or 0.8),
        "recovery_integrity": 1.0 if recovery.get("stable") else 0.7,
        "calmness_integrity": 1.0 if (truth.get("runtime_calmness_lock") or {}).get("locked") else 0.85,
        "branding_integrity": 1.0 if truth.get("operator_facing_branding_locked") else 0.9,
        "setup_integrity": 1.0 if truth.get("setup_ready_state_locked") else 0.85,
    }
    if readiness.get("state") == "critical":
        blocking.append("readiness_critical")
    if not schema.get("valid"):
        blocking.extend(schema.get("warnings") or [])
    integrity_score = round(sum(scores.values()) / max(1, len(scores)), 3)
    production_ready = integrity_score >= 0.85 and not blocking
    return {
        "runtime_integrity_certification": {
            "enterprise_grade": production_ready,
            "integrity_score": integrity_score,
            "production_ready": production_ready,
            "blocking_issues": blocking,
            "categories": {k: scores.get(k, 0.0) for k in INTEGRITY_CATEGORIES},
            "phase": "phase4_step22",
            "bounded": True,
        }
    }


def build_enterprise_runtime_integrity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    cert = build_runtime_integrity_certification(truth)["runtime_integrity_certification"]
    return {
        "enterprise_runtime_integrity": {
            **cert,
            "enterprise_runtime_assurance": cert.get("enterprise_grade"),
            "bounded": True,
        }
    }
