# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.office_operational_authority import build_office_operational_authority
from app.services.runtime.runtime_launch_orchestration import OFFICE_HOME_INTRO


def test_office_primary_entrypoint() -> None:
    blob = build_office_operational_authority({})
    office = blob.get("office_operational_authority") or {}
    assert office.get("authoritative_command_center") is True or office.get("primary_entrypoint") is True


def test_office_home_intro_copy() -> None:
    assert "operational command center" in OFFICE_HOME_INTRO.lower()
