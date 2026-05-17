# SPDX-License-Identifier: Apache-2.0

from pathlib import Path


def test_mission_control_nav_has_supervision() -> None:
    nav = Path(__file__).resolve().parents[1] / "web" / "lib" / "navigation.ts"
    text = nav.read_text(encoding="utf-8")
    assert "runtime-supervision" in text
    assert "Runtime supervision" in text
