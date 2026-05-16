# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_agent_result_query import test_idle_agent_no_task_message


def test_e2e_create_then_query_idle() -> None:
    test_idle_agent_no_task_message()
