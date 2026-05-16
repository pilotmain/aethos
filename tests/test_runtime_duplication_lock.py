# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_duplication_lock import build_runtime_duplication_lock


def test_runtime_duplication_lock_authority() -> None:
    out = build_runtime_duplication_lock({})
    lock = out["runtime_duplication_lock"]
    assert lock["single_truth_authority"] is True
    assert "build_runtime_truth" in lock["authoritative"]
