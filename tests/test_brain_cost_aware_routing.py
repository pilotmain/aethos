# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.brain.brain_selection import select_brain_for_task


def test_cost_estimate_on_selection() -> None:
    s = select_brain_for_task("repair_plan")
    assert "cost_estimate" in s
    assert s["cost_estimate"] == 0.0 or isinstance(s["cost_estimate"], float)
