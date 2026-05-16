# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_confidence import build_operator_onboarding_visibility
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_onboarding_checks() -> None:
    truth = build_runtime_truth(user_id=None)
    ob = build_operator_onboarding_visibility(truth)
    assert 0 <= float(ob.get("readiness_score") or 0) <= 1
    assert len(ob.get("checks") or []) >= 4
