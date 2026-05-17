# SPDX-License-Identifier: Apache-2.0

from aethos_cli.setup_conversational import SETUP_GLOBAL_COMMANDS


def test_enterprise_setup_experience_commands() -> None:
    assert "resume" in SETUP_GLOBAL_COMMANDS
    assert "repair" in SETUP_GLOBAL_COMMANDS
