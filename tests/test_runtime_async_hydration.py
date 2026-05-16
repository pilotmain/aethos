# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_async_hydration import hydrate_progressive_truth
from app.services.mission_control.runtime_priority_scheduler import slices_up_to_tier


def test_slices_up_to_critical() -> None:
    s = slices_up_to_tier("critical")
    assert "core" in s
    assert "derived" not in s


def test_progressive_hydration_partial() -> None:
    truth = hydrate_progressive_truth(user_id="test_user", max_tier="critical")
    assert truth.get("hydration_progress", {}).get("partial") is True
