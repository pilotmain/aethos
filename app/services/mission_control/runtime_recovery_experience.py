# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Launch-grade recovery experience copy (Phase 4 Step 13)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_recovery_center import build_runtime_recovery_center
from app.services.mission_control.runtime_restart_manager import build_runtime_restarts


def build_runtime_recovery_experience(truth: dict[str, Any] | None = None, *, user_id: str | None = None) -> dict[str, Any]:
    truth = truth or {}
    center = build_runtime_recovery_center(truth, user_id=user_id)
    restarts = build_runtime_restarts(truth)
    status = center.get("operational_status") or "healthy"
    messages = {
        "headline": _headline(status),
        "recovery_progress": _progress(truth, center),
        "operator_action": _operator_action(status, center),
        "what_remains_available": _available(status),
        "estimated_readiness": "immediate" if status == "healthy" else "progressive",
    }
    return {
        "runtime_recovery_experience": messages,
        "recovery_center": center,
        "restart_history": restarts.get("restart_history"),
        "restart_recommendations": restarts.get("runtime_restart_recommendations"),
        "hydration_status": truth.get("runtime_async_hydration") or truth.get("hydration_progress"),
        "provider_fallback_state": (truth.get("routing_summary") or {}).get("fallback_used"),
        "bounded": True,
    }


def _headline(status: str) -> str:
    if status in ("degraded", "partial", "stale"):
        return "AethOS runtime is reconnecting. Operational continuity is being restored."
    if status == "recovering":
        return "AethOS is recovering — summaries remain available while details hydrate."
    return "AethOS runtime is healthy and operationally calm."


def _progress(truth: dict[str, Any], center: dict[str, Any]) -> str:
    if center.get("stale_caches"):
        return "Serving cached operational truth while hydration completes."
    if center.get("failed_slices"):
        return f"Rebuilding slices: {', '.join(center.get('failed_slices') or [])[:3]}."
    return "All operational slices current."


def _operator_action(status: str, center: dict[str, Any]) -> str | None:
    if status in ("degraded", "partial"):
        return "Run aethos restart connection if Mission Control stays partial."
    if center.get("recovery_recommendations"):
        return (center["recovery_recommendations"][0] or {}).get("detail")
    return None


def _available(status: str) -> list[str]:
    if status == "healthy":
        return ["office", "summaries", "routing", "governance", "workers"]
    return ["office_summary", "cached_truth", "recovery_center", "advisories"]
