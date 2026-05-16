# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_panels import build_runtime_panels


def test_privacy_panel() -> None:
    p = build_runtime_panels(None)
    pr = p.get("privacy_runtime") or {}
    assert "mode" in pr
