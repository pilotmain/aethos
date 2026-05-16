# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_cohesion import (
    build_operational_summary,
    build_runtime_cleanup_progression,
    derive_operational_views_from_truth,
)
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_derive_views_from_truth() -> None:
    truth = {"runtime_workers": {}, "runtime_recommendations": {"recommendations": []}, "operational_intelligence": {}}
    views = derive_operational_views_from_truth(truth)
    assert "workers" in views
    assert "recommendations" in views


def test_truth_has_cohesion_keys() -> None:
    truth = build_runtime_truth()
    assert "runtime_cohesion" in truth
    assert "enterprise_operational_health" in truth
    assert "unified_operational_timeline" in truth


def test_cleanup_progression() -> None:
    p = build_runtime_cleanup_progression()
    assert p.get("progress_score", 0) > 0


def test_operational_summary() -> None:
    truth = {
        "runtime_health": {"status": "healthy"},
        "operational_intelligence": {"summaries": {}},
        "runtime_recommendations": {"recommendations": []},
        "enterprise_runtime_panels": {},
    }
    s = build_operational_summary(truth)
    assert s.get("single_truth_path") is True
    assert "headline" in s
