# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.operational_calmness import build_operational_quality, build_runtime_calmness
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_calmness_on_truth() -> None:
    truth = build_runtime_truth(user_id=None)
    assert truth.get("runtime_calmness")
    assert truth.get("operational_quality")


def test_calm_score_range() -> None:
    calm = build_runtime_calmness({})
    assert 0.0 <= float(calm.get("calm_score") or 0) <= 1.0
    qual = build_operational_quality({})
    assert 0.0 <= float(qual.get("quality_score") or 0) <= 1.0
