# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_launch_orchestration import build_runtime_continuity_message


def test_first_launch_experience_office_redirect_intent() -> None:
    from app.services.mission_control.office_operational_authority import build_office_operational_authority

    office = build_office_operational_authority({})["office_operational_authority"]
    assert office.get("authoritative_command_center") is True or office.get("primary_entrypoint") is True


def test_runtime_continuity_message_on_restart() -> None:
    assert "restoring" in build_runtime_continuity_message(restarting=True).lower()
