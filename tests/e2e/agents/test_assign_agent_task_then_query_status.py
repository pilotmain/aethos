# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_agent_task_assignment_visibility import test_create_agent_task_tracked


def test_e2e_assign_then_query_status() -> None:
    test_create_agent_task_tracked()
