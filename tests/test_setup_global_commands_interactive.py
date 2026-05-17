# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from aethos_cli.setup_conversational import SETUP_GLOBAL_COMMANDS, handle_setup_global_command
from aethos_cli.setup_prompt_runtime import _handle_command, set_prompt_context


def test_global_commands_complete() -> None:
    required = {"help", "why", "skip", "back", "resume", "status", "recommended", "current", "repair", "quit"}
    assert required <= set(SETUP_GLOBAL_COMMANDS)


def test_handle_command_help_returns_continue() -> None:
    set_prompt_context(section="welcome")
    assert _handle_command("help", label="x", default=None, recommended=None, allow_skip=True, hide=False) == "continue"


def test_conversational_help_handler() -> None:
    assert handle_setup_global_command("help") is True
