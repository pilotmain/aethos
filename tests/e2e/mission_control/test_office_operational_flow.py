# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.office_operational import build_office_operational_view
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_office_flow_from_truth() -> None:
    truth = build_runtime_truth(user_id=None)
    office = build_office_operational_view(truth)
    assert office.get("orchestrator", {}).get("role") == "orchestrator"
