# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_ownership_lock import build_runtime_ownership_status


def test_startup_process_integrity_conflict_flag() -> None:
    st = build_runtime_ownership_status()["runtime_ownership"]
    assert "conflict_detected" in st
