# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.execution_visibility import build_execution_visibility
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_execution_visibility_on_truth() -> None:
    truth = build_runtime_truth(user_id=None)
    assert truth.get("execution_visibility")
    assert truth.get("execution_chains") is not None
    assert truth.get("execution_governance")
    assert truth.get("execution_trace_health")


def test_execution_chains_bounded() -> None:
    vis = build_execution_visibility({})
    assert vis.get("chain_count", 0) <= 32
