# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_recovery_integrity import build_runtime_recovery_integrity


def test_recovery_integrity_shape() -> None:
    out = build_runtime_recovery_integrity({})["runtime_recovery_integrity"]
    assert out.get("explainable") is True
    assert "categories_tracked" in out
