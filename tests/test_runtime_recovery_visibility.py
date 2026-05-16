# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_panels import build_runtime_panels


def test_recovery_panel() -> None:
    p = build_runtime_panels(None)
    rec = p.get("recovery") or {}
    assert "continuity" in rec
