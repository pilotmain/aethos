# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_cleanup_completion import build_cleanup_completion
from app.services.mission_control.runtime_cohesion import build_runtime_cleanup_progression
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_cleanup_completion_locked() -> None:
    c = build_cleanup_completion()
    assert float(c.get("cleanup_completion_percentage") or 0) >= 0.95
    assert c.get("locked") is True
    assert c.get("deprecated_runtime_paths")


def test_cleanup_on_truth() -> None:
    truth = build_runtime_truth(user_id=None)
    assert truth.get("cleanup_completion")
    prog = build_runtime_cleanup_progression()
    assert prog.get("cleanup_locked") is True
