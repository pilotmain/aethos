# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_health_model import build_consolidated_runtime_health


def test_consolidated_health_healthy() -> None:
    h = build_consolidated_runtime_health({"reliability": {"integrity_ok": True}, "queued_tasks": 0})
    assert h["status"] == "healthy"
    assert h["severity"] == "info"
    assert h["queue_pressure"] is False


def test_consolidated_health_critical() -> None:
    h = build_consolidated_runtime_health(
        {"reliability": {"integrity_ok": False}},
        events=[{"severity": "critical"}],
    )
    assert h["status"] == "critical"
