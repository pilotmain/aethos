# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from aethos_cli import restart_cli


def test_restart_cli_imports() -> None:
    assert callable(restart_cli.cmd_restart)
