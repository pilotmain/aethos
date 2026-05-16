# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.mission_control_language_system import translate_term, build_mission_control_language_system


def test_language_system() -> None:
    assert translate_term("degraded") == "Needs attention"
    assert build_mission_control_language_system()["tone"] == "enterprise_calm"
