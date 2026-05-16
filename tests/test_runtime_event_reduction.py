# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_event_intelligence import aggregate_events_for_display, normalize_runtime_event, persist_runtime_event


def test_aggregate_collapses_duplicates() -> None:
    for _ in range(3):
        persist_runtime_event(normalize_runtime_event("repair_started", payload={"project_id": "a"}))
    rows = aggregate_events_for_display(limit=10)
    repair = [r for r in rows if r.get("event_type") == "repair_started"]
    assert repair and int(repair[0].get("count") or 1) >= 2
