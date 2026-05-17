# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_recovery_authority import build_runtime_recovery_authority


def test_runtime_recovery_authority() -> None:
    blob = build_runtime_recovery_authority({})
    assert blob["runtime_recovery_authority"]["recovery_ready"] is True
    assert blob["runtime_recovery_confidence"]["calm"] is True
