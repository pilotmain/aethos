# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.office_operational_authority import build_office_operational_authority


def test_office_authority() -> None:
    out = build_office_operational_authority({"runtime_readiness_score": 0.9})
    assert out["office_operational_authority"]["authoritative_command_center"] is True
