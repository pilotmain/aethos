# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from unittest.mock import patch

from aethos_cli.setup_interactive_mode import attach_setup_tty, setup_interactive
from aethos_cli.setup_prompt_runtime import prompt_select, set_prompt_context


def test_prompt_select_uses_default_when_noninteractive() -> None:
    set_prompt_context(section="welcome")
    with patch.dict(os.environ, {"NEXA_NONINTERACTIVE": "1"}, clear=False):
        value = prompt_select(
            "Test",
            [("A", "a", ""), ("B", "b", "")],
            default_index=2,
        )
    assert value == "b"


def test_setup_interactive_false_when_ci() -> None:
    with patch.dict(os.environ, {"AETHOS_SETUP_CI": "1", "NEXA_NONINTERACTIVE": ""}, clear=False):
        assert setup_interactive() is False


def test_attach_tty_when_dev_tty_exists() -> None:
    with patch("aethos_cli.setup_interactive_mode.noninteractive_setup", return_value=False):
        with patch("sys.stdin.isatty", side_effect=[False, True]):
            with patch("os.path.exists", return_value=True):
                with patch("os.open", return_value=3):
                    with patch("os.dup2"):
                        with patch("os.close"):
                            assert attach_setup_tty() is True
