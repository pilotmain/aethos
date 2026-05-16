# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_health_model import build_consolidated_runtime_health


def test_health_exposes_pressure_flags() -> None:
    h = build_consolidated_runtime_health(
        {"queued_tasks": 12, "retrying_tasks": 2, "reliability": {"queue_pressure_events": 1}},
    )
    assert h["queue_pressure"] is True
    assert h["retry_pressure"] is True
