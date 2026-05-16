# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from aethos_cli.setup_prompt_runtime import _handle_command, set_prompt_context


def test_setup_global_command_help() -> None:
    set_prompt_context(section="providers")
    assert _handle_command("help", label="API key", default=None, recommended=None, allow_skip=True, hide=True) == "continue"


def test_setup_global_command_recommended() -> None:
    set_prompt_context(section="providers")
    assert (
        _handle_command(
            "recommended",
            label="x",
            default="a",
            recommended="hybrid",
            allow_skip=True,
            hide=False,
        )
        == "recommended"
    )
