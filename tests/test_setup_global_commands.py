# SPDX-License-Identifier: Apache-2.0

from aethos_cli.setup_conversational import SETUP_GLOBAL_COMMANDS


def test_setup_global_commands_complete() -> None:
    required = {"help", "why", "skip", "back", "resume", "status", "recommended", "current", "repair", "quit"}
    assert required <= set(SETUP_GLOBAL_COMMANDS)
