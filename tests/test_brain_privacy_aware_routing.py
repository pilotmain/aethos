# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.brain.brain_selection import select_brain_for_task


def test_privacy_mode_on_selection() -> None:
    s = select_brain_for_task("repair_plan")
    assert "privacy_mode" in s
