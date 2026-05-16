# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Adaptive operational coordination signals (Phase 3 Step 11)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state


def build_coordination_signals(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    ort = truth.get("orchestration") or {}
    queues = truth.get("queues") or {}
    repairs = truth.get("repair") or {}
    workers = truth.get("runtime_workers") or {}
    signals: list[dict[str, Any]] = []

    active_workers = int((workers.get("active_worker_count") if isinstance(workers, dict) else 0) or 0)
    queued = int(queues.get("total") or truth.get("runtime_health", {}).get("queued_tasks") or 0)
    if active_workers > 0 and queued > active_workers * 4:
        signals.append({"kind": "worker_saturation", "severity": "warning", "message": "Queue depth exceeds worker capacity"})

    repair_count = len(repairs) if isinstance(repairs, dict) else 0
    if repair_count > 4:
        signals.append({"kind": "repair_duplication", "severity": "warning", "message": "Multiple concurrent repair contexts"})

    rel = (truth.get("runtime_metrics") or {}).get("runtime_reliability") or {}
    if int(rel.get("deployment_pressure_events") or 0) > 1:
        signals.append({"kind": "deployment_conflicts", "severity": "warning", "message": "Deployment pressure events detected"})

    if int(rel.get("provider_failures") or 0) > 0:
        signals.append({"kind": "provider_instability", "severity": "error", "message": "Provider instability — prioritize stability"})

    if int(rel.get("retry_pressure_events") or 0) > 0:
        signals.append({"kind": "repeated_retries", "severity": "warning", "message": "Retry pressure — collapse redundant operations"})

    conts = truth.get("worker_continuations") or []
    if isinstance(conts, list):
        stalled = sum(1 for c in conts if isinstance(c, dict) and str(c.get("status")) == "queued")
        if stalled > 6:
            signals.append({"kind": "stalled_continuations", "severity": "info", "message": f"{stalled} queued continuations"})

    health = str((truth.get("runtime_health") or {}).get("status") or "healthy")
    if health in ("degraded", "critical"):
        signals.append({"kind": "runtime_escalation", "severity": "error", "message": f"Runtime state {health} — escalate recovery"})

    dup_prevented = _estimate_duplication_prevented(truth)
    return {
        "signals": signals[:12],
        "coordination_health": "stable" if not signals else "attention",
        "duplication_prevented_estimate": dup_prevented,
        "prioritize_stability": health in ("degraded", "critical", "warning"),
    }


def record_coordination_action(kind: str, *, detail: str = "") -> None:
    from app.services.mission_control.runtime_metrics_discipline import record_discipline_counter

    record_discipline_counter(f"coordination_{kind}", detail=detail)


def _estimate_duplication_prevented(truth: dict[str, Any]) -> int:
    events = truth.get("runtime_events") or []
    if not isinstance(events, list):
        return 0
    collapsed = sum(max(0, int(e.get("count") or 1) - 1) for e in events if isinstance(e, dict))
    return collapsed
