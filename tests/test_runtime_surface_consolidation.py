# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_surface_consolidation import build_runtime_surface_consolidation


def test_runtime_surface_consolidation() -> None:
    out = build_runtime_surface_consolidation()
    assert out["runtime_surface_consolidation"]["single_operational_story"] is True
    assert "office" in out["runtime_surface_consolidation"]["surfaces"]
