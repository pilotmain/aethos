# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Launch-grade operational focus — priority work and noise reduction (Phase 4 Step 13)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.operator_trust_experience import build_runtime_focus_mode
from app.services.mission_control.operational_calmness_lock import build_calmness_lock


def build_runtime_noise_reduction(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    lock = build_calmness_lock(truth)
    return {
        "noise_reduction_ratio": lock.get("operational_noise_reduction"),
        "duplicate_chatter_suppressed": True,
        "repetitive_warnings_collapsed": True,
        "low_value_events_filtered": True,
        "bounded": True,
    }


def build_runtime_priority_work(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    items: list[dict[str, str]] = []
    for esc in ((truth.get("runtime_escalations") or {}).get("active_escalations") or [])[:3]:
        if isinstance(esc, dict):
            items.append({"kind": "escalation", "summary": str(esc.get("type") or "issue")[:80]})
    for rec in (truth.get("strategic_recommendations") or [])[:2]:
        if isinstance(rec, dict):
            items.append({"kind": "advisory", "summary": str(rec.get("message") or rec.get("title") or "")[:80]})
    office = truth.get("office") or {}
    if office.get("active_tasks"):
        items.append({"kind": "work", "summary": f"{office.get('active_tasks')} active tasks"})
    return {"priority_items": items[:8], "count": len(items), "bounded": True}


def build_runtime_operational_focus_launch(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    focus = build_runtime_focus_mode(truth)
    return {
        "operational_focus": {
            **focus,
            "launch_grade": True,
            "command_center": True,
        },
        "priority_work": build_runtime_priority_work(truth),
        "noise_reduction": build_runtime_noise_reduction(truth),
        "health_first": True,
    }
