# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_event_intelligence import aggregate_events_for_display


def test_office_event_limit_small() -> None:
    events = aggregate_events_for_display(limit=10, suppress_info_when_noisy=True)
    assert len(events) <= 10
