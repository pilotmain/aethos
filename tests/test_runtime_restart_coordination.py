# SPDX-License-Identifier: Apache-2.0

from aethos_cli import restart_cli


def test_restart_cli_exports_coordination_helper() -> None:
    assert hasattr(restart_cli, "cmd_restart")
