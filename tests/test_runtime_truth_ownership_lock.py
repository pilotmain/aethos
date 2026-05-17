# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_truth_ownership_lock import (
    build_runtime_truth_authority,
    release_truth_hydration_lock_if_owner,
    try_acquire_truth_hydration_lock,
)


def test_truth_ownership_lock() -> None:
    release_truth_hydration_lock_if_owner()
    assert try_acquire_truth_hydration_lock(cycle="test") is True
    blob = build_runtime_truth_authority()
    assert blob["duplicate_hydration_prevented"] is True
    release_truth_hydration_lock_if_owner()
