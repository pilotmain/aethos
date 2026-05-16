# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.automation_governance import build_automation_governance, build_automation_trust


def test_automation_governance_operator_approved() -> None:
    gov = build_automation_governance({})
    assert gov.get("operator_approved") is True
    trust = build_automation_trust({})
    assert trust.get("operator_triggered_only") is True
