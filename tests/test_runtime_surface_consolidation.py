# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_surface_consolidation import build_runtime_surface_consolidation


def test_surface_consolidation_step22() -> None:
    out = build_runtime_surface_consolidation()["runtime_surface_consolidation"]
    assert out.get("phase") == "phase4_step22"
    assert "authoritative_surfaces" in out
