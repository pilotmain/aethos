# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.operational_trust import build_operational_trust_model
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_operational_trust_keys() -> None:
    truth = build_runtime_truth(user_id=None)
    assert truth.get("operational_trust_score") is not None
    assert truth.get("governance_integrity")
    assert truth.get("runtime_accountability")
    assert truth.get("provider_trust")
    assert truth.get("automation_trust")
    assert truth.get("worker_trust")


def test_trust_score_range() -> None:
    model = build_operational_trust_model({})
    score = float(model.get("operational_trust_score") or 0)
    assert 0.0 <= score <= 1.0
