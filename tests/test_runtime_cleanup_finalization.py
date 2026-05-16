# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_cohesion import build_runtime_cleanup_progression


def test_cleanup_progression_step15() -> None:
    prog = build_runtime_cleanup_progression()
    assert float(prog.get("progress_score") or 0) >= 0.9
    assert "unified_worker_state" in str(prog.get("disconnected_worker_state", ""))
