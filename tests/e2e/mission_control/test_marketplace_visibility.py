# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth


def test_truth_includes_marketplace() -> None:
    t = build_runtime_truth(user_id=None)
    assert "marketplace" in t
    assert "operational_intelligence" in t
