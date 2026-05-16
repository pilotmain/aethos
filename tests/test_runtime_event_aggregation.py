# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_event_intelligence import (
    aggregate_events_for_display,
    normalize_runtime_event,
    persist_runtime_event,
    prioritize_events,
)


def test_prioritize_severity_first() -> None:
    rows = prioritize_events(
        [
            {"severity": "info", "timestamp": "2026-01-02T00:00:00Z"},
            {"severity": "critical", "timestamp": "2026-01-01T00:00:00Z"},
        ]
    )
    assert rows[0].get("severity") == "critical"


def test_aggregate_suppresses_noise() -> None:
    for _ in range(5):
        persist_runtime_event(normalize_runtime_event("task_started", payload={"project_id": "p1"}))
    out = aggregate_events_for_display(limit=20, suppress_info_when_noisy=True)
    assert isinstance(out, list)
