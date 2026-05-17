# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_continuity_certification import build_runtime_continuity_certification


def test_continuity_certification() -> None:
    out = build_runtime_continuity_certification({})["runtime_continuity_certification"]
    assert "domains" in out
    assert out.get("phase") == "phase4_step23"
