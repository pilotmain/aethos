# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.enterprise_operator_experience import build_enterprise_operator_experience
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_enterprise_operator_experience_keys() -> None:
    truth = build_runtime_truth(user_id=None)
    exp = truth.get("enterprise_operator_experience") or {}
    assert exp.get("cohesive") is True
    assert exp.get("runtime_overview")
    assert truth.get("runtime_overview")


def test_operator_experience_builder() -> None:
    out = build_enterprise_operator_experience({})
    assert out.get("single_truth_path") is True
