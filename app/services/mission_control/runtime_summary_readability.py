# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Human-readable operational summaries (Phase 3 Step 4)."""

from __future__ import annotations

from typing import Any


def humanize_repair_summary(repair: dict[str, Any]) -> str:
    if not isinstance(repair, dict):
        return "No repair context"
    status = repair.get("status") or "unknown"
    pid = repair.get("project_id") or repair.get("repair_context_id") or "project"
    verified = (repair.get("verification_result") or {}).get("verified")
    if verified is True:
        return f"Repair on {pid} verified successfully"
    if verified is False:
        return f"Repair on {pid} failed verification"
    return f"Repair on {pid}: {status}"


def humanize_deployment_summary(deployment: dict[str, Any]) -> str:
    if not isinstance(deployment, dict):
        return "No deployment"
    prov = deployment.get("provider") or "provider"
    pid = deployment.get("project_id") or deployment.get("id") or "project"
    status = deployment.get("status") or "active"
    return f"{prov} deployment for {pid} — {status}"


def humanize_provider_action(action: dict[str, Any]) -> str:
    if not isinstance(action, dict):
        return "Provider action"
    prov = action.get("provider") or action.get("provider_id") or "provider"
    op = action.get("action") or action.get("operation") or "operation"
    st = action.get("status") or ""
    return f"{prov} {op}" + (f" ({st})" if st else "")


def build_readable_summaries(truth: dict[str, Any]) -> dict[str, Any]:
    repairs = truth.get("repair") or {}
    latest: list[str] = []
    if isinstance(repairs, dict):
        for pid, row in list(repairs.items())[:8]:
            if isinstance(row, dict):
                latest.append(humanize_repair_summary({**row, "project_id": pid}))
    provider_actions = (truth.get("providers") or {}).get("recent_actions") or []
    return {
        "repairs": latest,
        "provider_actions": [humanize_provider_action(a) for a in provider_actions[-6:] if isinstance(a, dict)],
        "runtime_health": _health_sentence(truth.get("runtime_health") or {}),
    }


def _health_sentence(health: dict[str, Any]) -> str:
    st = health.get("status") or "healthy"
    parts = [f"Runtime is {st}"]
    if health.get("queue_pressure"):
        parts.append("queue pressure elevated")
    if health.get("retry_pressure"):
        parts.append("retries active")
    return " · ".join(parts)
