# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.mission_control_production_discipline import build_mission_control_production_discipline


def test_mc_production_discipline() -> None:
    out = build_mission_control_production_discipline({})["mission_control_production_discipline"]
    assert out.get("calm") is True
    assert out.get("office_authoritative_entry") is True
