# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_process_group_manager import build_process_group_status


def test_runtime_process_recovery_status() -> None:
    assert build_process_group_status()["runtime_process_group"]["phase"] == "phase4_step25"
