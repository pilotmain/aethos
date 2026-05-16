# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_health_model import build_consolidated_runtime_health


def test_health_status_enum() -> None:
    h = build_consolidated_runtime_health({"reliability": {"integrity_ok": True}, "queued_tasks": 0})
    assert h["status"] in ("healthy", "warning", "degraded", "critical")
