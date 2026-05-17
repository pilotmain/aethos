# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_process_group_manager import terminate_runtime_process_groups


def test_runtime_restart_coordination_stop() -> None:
    result = terminate_runtime_process_groups(force=False)
    assert result.get("ok") is True
