# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_event_intelligence import aggregate_events_for_display


def test_collapsed_events_have_count() -> None:
    rows = aggregate_events_for_display(limit=20, suppress_info_when_noisy=True)
    for r in rows:
        assert "count" in r or "event_type" in r
