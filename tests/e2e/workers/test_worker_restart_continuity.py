# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_worker_continuation_recovery import test_recover_running_tasks


def test_e2e_restart_continuity() -> None:
    test_recover_running_tasks()
