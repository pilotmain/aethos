# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_truth_schema_lock import (
    RUNTIME_TRUTH_CONTRACT_VERSION,
    build_runtime_truth_schema_lock,
)


def test_runtime_truth_schema_lock() -> None:
    out = build_runtime_truth_schema_lock({"runtime_resilience": {}, "hydration_progress": {}})
    lock = out["runtime_truth_schema_lock"]
    assert lock["contract_version"] == RUNTIME_TRUTH_CONTRACT_VERSION
    assert "missing_required" in lock
