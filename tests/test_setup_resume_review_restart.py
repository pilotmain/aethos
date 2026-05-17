# SPDX-License-Identifier: Apache-2.0

from aethos_cli.setup_conversational import SETUP_GLOBAL_COMMANDS


def test_resume_menu_commands_present() -> None:
    assert "resume" in SETUP_GLOBAL_COMMANDS
    assert "repair" in SETUP_GLOBAL_COMMANDS
    assert "status" in SETUP_GLOBAL_COMMANDS
