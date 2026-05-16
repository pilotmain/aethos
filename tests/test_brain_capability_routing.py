# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.brain.brain_capabilities import BRAIN_TASKS, score_brain_for_task


def test_brain_tasks_defined() -> None:
    assert "repair_planning" in BRAIN_TASKS
    assert score_brain_for_task("ollama", "repair_planning", local_first=True) > 0
