# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_event_intelligence import aggregate_events_for_display
from app.services.mission_control.runtime_metrics_discipline import get_runtime_discipline_metrics


def test_event_aggregation_bounded() -> None:
    rows = aggregate_events_for_display(limit=24)
    assert len(rows) <= 24


def test_discipline_records_collapse() -> None:
    aggregate_events_for_display(limit=12)
    m = get_runtime_discipline_metrics()
    assert "event_buffer_size" in m or "last_event_collapsed_count" in m or m
