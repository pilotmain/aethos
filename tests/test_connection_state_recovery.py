# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_hydration_scheduler import (
    begin_hydration_cycle,
    end_hydration_cycle,
    should_defer_state_write,
)


def test_hydration_cycle_defer_writes() -> None:
    assert should_defer_state_write() is False
    gid = begin_hydration_cycle()
    assert should_defer_state_write() is True
    summary = end_hydration_cycle(duration_ms=12.0)
    assert summary["hydration_generation_id"] == gid
    assert should_defer_state_write() is False
