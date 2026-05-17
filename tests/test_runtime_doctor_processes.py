# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_supervision import build_runtime_supervision


def test_doctor_supervision_bundle() -> None:
    sup = build_runtime_supervision()
    assert sup["runtime_supervision"]["supervision_verified"] is True
