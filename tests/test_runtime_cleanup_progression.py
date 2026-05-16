# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_cohesion import build_runtime_cleanup_progression


def test_cleanup_notes() -> None:
    p = build_runtime_cleanup_progression()
    assert "duplicate_truth_builders" in p
    assert isinstance(p.get("notes"), list)
