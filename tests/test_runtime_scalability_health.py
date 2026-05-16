# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth


def test_scalability_health_keys() -> None:
    truth = build_runtime_truth(user_id=None)
    assert truth.get("runtime_scalability_health")
    assert truth.get("operational_pressure")
    assert truth.get("runtime_query_efficiency")
    assert truth.get("governance_scalability")
    assert truth.get("enterprise_operational_views")
