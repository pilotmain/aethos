# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_operator_experience import build_runtime_operator_experience


def test_runtime_operator_experience() -> None:
    out = build_runtime_operator_experience({})
    assert out["runtime_operator_experience"]["cohesive"] is True
    assert out["marketplace_clarity"]["runtime_plugin"]
