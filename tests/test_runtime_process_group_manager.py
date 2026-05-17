# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_process_group_manager import build_process_group_status


def test_process_group_status() -> None:
    blob = build_process_group_status()
    assert blob["runtime_process_group"]["orphan_prevention"] is True
