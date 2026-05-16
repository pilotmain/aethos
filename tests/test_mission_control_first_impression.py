# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.setup.setup_first_impression import build_setup_first_impression


def test_mission_control_first_impression() -> None:
    out = build_setup_first_impression()
    fi = out["setup_first_impression"]
    assert "AethOS" in fi["greeting"]
    assert fi["recommended_next_steps"]
