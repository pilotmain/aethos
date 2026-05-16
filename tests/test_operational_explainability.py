# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.operational_explainability import build_operational_explainability
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_explainability_on_truth() -> None:
    truth = build_runtime_truth(user_id=None)
    exp = truth.get("operational_explainability") or {}
    assert exp.get("concise") is True
    assert "explanations" in exp


def test_explainability_shape() -> None:
    out = build_operational_explainability({})
    assert "worker_selection" in out
