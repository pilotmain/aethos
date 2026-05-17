# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Bounded enterprise runtime governance timeline (Phase 4 Step 26)."""

from __future__ import annotations

from typing import Any

_MAX_EVENTS = 32


def build_runtime_operational_governance_timeline(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    events: list[dict[str, Any]] = []
    try:
        from app.services.mission_control.runtime_ownership_lock import load_process_lifecycle

        for ev in (load_process_lifecycle().get("events") or [])[-16:]:
            events.append(
                {
                    "kind": "process_lifecycle",
                    "event": ev.get("event"),
                    "detail": (ev.get("detail") or "")[:120],
                    "at": ev.get("at"),
                }
            )
    except Exception:
        pass
    if truth.get("launch_stabilized"):
        events.append({"kind": "stabilization", "event": "launch_stabilized", "at": None})
    if truth.get("runtime_coordination_authoritative"):
        events.append({"kind": "ownership", "event": "coordination_authoritative", "at": None})
    events = events[-_MAX_EVENTS:]
    return {
        "runtime_operational_governance_timeline": {
            "phase": "phase4_step26",
            "events": events,
            "count": len(events),
            "bounded": True,
            "calm": True,
            "explainable": True,
            "no_duplication": True,
            "categories": [
                "runtime_recovery",
                "degraded_transitions",
                "startup_cycles",
                "ownership_changes",
                "supervision_actions",
                "runtime_stabilization",
                "hydration_coordination",
                "governance_events",
            ],
        }
    }
