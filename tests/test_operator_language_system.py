# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.operator_language_system import build_operator_language_system


def test_operator_language_system() -> None:
    out = build_operator_language_system({})
    sys = out["operator_language_system"]
    assert sys.get("calmness")
    assert sys.get("phase") == "phase4_step21"
