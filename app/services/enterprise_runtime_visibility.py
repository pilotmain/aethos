# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise runtime visibility panels (Phase 3 Step 10)."""

from __future__ import annotations

from typing import Any

from app.runtime.automation_pack_runtime import build_automation_pack_runtime_truth
from app.services.mission_control.runtime_confidence import build_runtime_confidence
from app.services.operational_intelligence_engine import build_operational_intelligence_engine
from app.services.workspace_runtime_intelligence import build_operational_risk, build_workspace_intelligence


def build_enterprise_runtime_panels(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    engine = build_operational_intelligence_engine(truth.get("orchestration"))
    risk = build_operational_risk()
    workspace = build_workspace_intelligence()
    packs = build_automation_pack_runtime_truth()
    conf = truth.get("runtime_confidence") or build_runtime_confidence(truth)

    return {
        "runtime_reliability": {
            "health": (conf.get("runtime_confidence") or {}).get("health"),
            "operational_stability": conf.get("operational_stability"),
        },
        "automation_health": {
            "pack_count": packs.get("pack_count"),
            "recent_executions": len(packs.get("recent_executions") or []),
            "failed_packs": sum(1 for p in packs.get("packs") or [] if p.get("failed")),
        },
        "governance_health": {
            "summary": engine.get("summaries", {}).get("governance_summary"),
            "enterprise_state": engine.get("enterprise_operational_state"),
        },
        "operational_risk": risk,
        "provider_stability": conf.get("provider_reliability") or {},
        "deployment_reliability": conf.get("deployment_confidence") or {},
        "worker_reliability": engine.get("worker_reliability") or {},
        "workspace_health": {
            "confidence": workspace.get("workspace_confidence"),
            "risk_signals": workspace.get("risk_signals"),
            "project_count": workspace.get("project_count"),
        },
    }
