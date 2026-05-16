# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.enterprise_readiness import build_enterprise_readiness, build_runtime_readiness_score
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_enterprise_readiness_on_truth() -> None:
    truth = build_runtime_truth(user_id=None)
    assert truth.get("enterprise_readiness")
    assert truth.get("runtime_readiness_score") is not None
    assert truth.get("operational_readiness")
    assert truth.get("governance_readiness")


def test_readiness_score_range() -> None:
    score = build_runtime_readiness_score({})
    assert 0.0 <= score <= 1.0
