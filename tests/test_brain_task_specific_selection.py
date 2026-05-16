# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.brain.brain_selection import select_brain_for_task


def test_task_recorded() -> None:
    s = select_brain_for_task("deployment_diagnosis")
    assert s.get("task") == "deployment_diagnosis"
