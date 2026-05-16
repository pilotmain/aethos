# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth


def test_enterprise_runtime_views() -> None:
    truth = build_runtime_truth(user_id=None)
    views = truth.get("enterprise_runtime_views") or {}
    assert views.get("runtime_overview")
    assert views.get("governance_oversight")
