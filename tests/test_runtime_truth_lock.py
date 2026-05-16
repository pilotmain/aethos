# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth
from app.services.mission_control.runtime_truth_lock import build_truth_lock_status, validate_truth_discipline


def test_truth_lock_on_full_truth() -> None:
    truth = build_runtime_truth(user_id=None)
    lock = truth.get("truth_lock") or {}
    assert lock.get("single_truth_path") is True


def test_validate_empty_truth_warns() -> None:
    v = validate_truth_discipline({})
    assert v.get("truth_fragmentation") or v.get("disconnected_surfaces")
