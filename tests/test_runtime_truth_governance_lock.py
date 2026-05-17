# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_truth_governance_lock import build_runtime_truth_governance_lock


def test_runtime_truth_governance_lock() -> None:
    blob = build_runtime_truth_governance_lock({})
    assert blob["runtime_truth_governed"] is not None
    assert blob["runtime_truth_governance_lock"]["continuity_safe"] is True
