# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_event_intelligence import aggregate_events_for_display


def test_office_events_bounded() -> None:
    events = aggregate_events_for_display(limit=24, suppress_info_when_noisy=True)
    assert len(events) <= 24
    for row in events:
        assert row.get("event_type")
