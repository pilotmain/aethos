# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth


def test_execution_visibility_flow() -> None:
    truth = build_runtime_truth(user_id=None)
    vis = truth.get("execution_visibility") or {}
    assert vis.get("operator_readable") is True
    assert vis.get("privacy_aware") is True
