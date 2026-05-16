# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_panels import build_runtime_panels


def test_panels_include_operational_intelligence() -> None:
    panels = build_runtime_panels(None)
    assert panels.get("operational_intelligence") is not None
