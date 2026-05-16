# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from pathlib import Path

from app.services.mission_control.mission_control_cohesion import build_cohesion_report
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_cohesion_includes_confidence() -> None:
    truth = build_runtime_truth(user_id=None)
    report = build_cohesion_report(truth)
    assert "runtime_confidence" not in (report.get("missing_truth_keys") or [])


def test_trust_docs_exist() -> None:
    root = Path(__file__).resolve().parents[1] / "docs"
    for name in (
        "ENTERPRISE_RUNTIME_CONFIDENCE.md",
        "OPERATIONAL_TRUST_MODEL.md",
        "RUNTIME_STABILITY_SUMMARY.md",
        "COMMERCIAL_POSITIONING.md",
    ):
        assert (root / name).is_file(), name
