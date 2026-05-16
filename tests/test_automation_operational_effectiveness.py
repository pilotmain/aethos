# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.mission_control.automation_operational_effectiveness import (
    build_automation_operational_effectiveness,
)


def test_automation_effectiveness_operator_approved() -> None:
    out = build_automation_operational_effectiveness({})
    assert out.get("operator_approved") is True
    assert out.get("governance_visible") is True
