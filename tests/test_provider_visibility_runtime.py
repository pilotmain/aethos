# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_panels import build_runtime_panels


def test_provider_operations_panel() -> None:
    p = build_runtime_panels(None)
    po = p.get("provider_operations") or {}
    assert "inventory" in po
    assert "latest_repairs" in po
