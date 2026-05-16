# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth


def test_operational_readiness_flow() -> None:
    truth = build_runtime_truth(user_id=None)
    ready = truth.get("enterprise_readiness") or {}
    assert ready.get("enterprise_ready") in (True, False)
    assert truth.get("truth_lock")
