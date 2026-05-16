# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.governance_experience import build_governance_experience
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_governance_experience_on_truth() -> None:
    truth = build_runtime_truth(user_id=None)
    exp = truth.get("governance_experience") or {}
    assert exp.get("accountability_visible") is True


def test_governance_experience_searchable() -> None:
    exp = build_governance_experience({})
    assert exp.get("searchable") is True
