# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth


def test_worker_cohesion_keys() -> None:
    truth = build_runtime_truth(user_id=None)
    assert truth.get("unified_worker_state")
    assert truth.get("worker_operational_identity")
    assert truth.get("worker_runtime_cohesion", {}).get("cohesive") is True
