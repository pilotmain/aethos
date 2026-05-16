# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_perception_responsiveness import build_runtime_perception_responsiveness


def test_runtime_perception() -> None:
    out = build_runtime_perception_responsiveness({})
    assert out["hydration_stage"]
    assert out["operator_message"]
