# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise operational summarization — summary-first MC (Phase 4 Step 8)."""

from __future__ import annotations

from typing import Any


def build_operational_summary(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    health = (truth.get("enterprise_operational_health") or {}).get("status") or "nominal"
    return {
        "health": health,
        "readiness": truth.get("runtime_readiness_score"),
        "pressure": (truth.get("operational_pressure") or {}).get("level"),
    }


def build_worker_summary(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "ecosystem": (truth.get("worker_ecosystem_health") or {}).get("status"),
        "active": (truth.get("runtime_workers") or {}).get("active_count"),
        "trust": (truth.get("worker_trust_model") or {}).get("trust_indicator"),
    }


def build_governance_summary(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "readiness": (truth.get("governance_readiness") or {}).get("trust_score"),
        "escalations": (truth.get("runtime_escalations") or {}).get("escalation_count"),
        "searchable": (truth.get("governance_experience") or {}).get("searchable"),
    }


def build_deployment_summary(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"readiness": (truth or {}).get("deployment_readiness"), "learning": (truth or {}).get("deployment_learning")}


def build_provider_summary(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    routing = (truth or {}).get("routing_summary") or {}
    return {
        "primary": routing.get("primary_provider"),
        "fallback_used": routing.get("fallback_used"),
        "history": len((truth or {}).get("provider_operational_history", {}).get("routing_history") or []),
    }


def build_continuity_summary(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    c = (truth or {}).get("operational_continuity_engine") or {}
    return {
        "recovery_quality": c.get("continuity_recovery_quality"),
        "resume_available": (truth or {}).get("runtime_resume_state", {}).get("resume_available"),
    }


def build_enterprise_runtime_summaries(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "operational_summary": build_operational_summary(truth),
        "worker_summary": build_worker_summary(truth),
        "governance_summary": build_governance_summary(truth),
        "deployment_summary": build_deployment_summary(truth),
        "provider_summary": build_provider_summary(truth),
        "continuity_summary": build_continuity_summary(truth),
        "summary_first": True,
    }
