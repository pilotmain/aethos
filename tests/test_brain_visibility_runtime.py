# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.mission_control.runtime_truth import build_brain_visibility


def test_brain_visibility_shape() -> None:
    v = build_brain_visibility()
    brain = v.get("brain") or {}
    assert "privacy_mode" in brain
    assert "reason" in brain
    assert "local_first" in brain
