# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.operational_narratives import build_operational_narratives
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_narratives_bounded() -> None:
    truth = build_runtime_truth(user_id=None)
    block = truth.get("operational_narratives") or {}
    assert len(block.get("narratives") or []) <= 16
    assert block.get("bounded") is True


def test_narratives_shape() -> None:
    out = build_operational_narratives({})
    assert "narratives" in out
