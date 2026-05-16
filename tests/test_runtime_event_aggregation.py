# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_event_intelligence import (
    aggregate_events_for_display,
    filter_events_by_age,
    normalize_runtime_event,
    persist_runtime_event,
)


def test_aggregate_collapses_and_prioritizes() -> None:
    for _ in range(4):
        persist_runtime_event(normalize_runtime_event("task_started", payload={"project_id": "x"}))
    out = aggregate_events_for_display(limit=20)
    assert out
    assert any(int(r.get("count") or 1) >= 2 for r in out)


def test_filter_by_age_keeps_recent() -> None:
    row = normalize_runtime_event("test_event")
    kept = filter_events_by_age([row], max_age_hours=48)
    assert kept
