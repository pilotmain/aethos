# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_responsiveness_guarantees import build_runtime_responsiveness_guarantees


def test_responsiveness_guarantees() -> None:
    out = build_runtime_responsiveness_guarantees({})
    assert "office" in out["operational_surface_priorities"]
