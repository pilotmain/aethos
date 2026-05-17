# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from unittest.mock import patch

from aethos_cli.setup_interactive_mode import (
    SETUP_MODES,
    attach_setup_tty,
    initialize_setup_interactive,
    noninteractive_setup,
    resolve_setup_mode,
    setup_interactive,
)


def test_setup_modes_defined() -> None:
    assert "interactive" in SETUP_MODES
    assert "non_interactive" in SETUP_MODES
    assert "ci" in SETUP_MODES


def test_noninteractive_when_env_set() -> None:
    with patch.dict(os.environ, {"NEXA_NONINTERACTIVE": "1"}, clear=False):
        assert noninteractive_setup() is True
        assert setup_interactive() is False


def test_ci_mode_from_env() -> None:
    with patch.dict(os.environ, {"AETHOS_SETUP_CI": "1"}, clear=False):
        assert resolve_setup_mode() == "ci"


def test_repair_mode_from_install_kind() -> None:
    assert resolve_setup_mode(install_kind="repair") == "repair"


def test_initialize_sets_mode_env() -> None:
    with patch.dict(os.environ, {"NEXA_NONINTERACTIVE": "1"}, clear=False):
        mode = initialize_setup_interactive()
        assert mode == "non_interactive"
        assert os.environ.get("AETHOS_SETUP_MODE") == "non_interactive"


def test_attach_setup_tty_no_crash_without_tty() -> None:
    with patch("sys.stdin.isatty", return_value=False):
        with patch("os.path.exists", return_value=False):
            assert attach_setup_tty() is False
