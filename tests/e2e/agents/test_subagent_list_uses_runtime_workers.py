# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_agent_creation_runtime_worker import test_link_registry_creates_runtime_worker


def test_e2e_subagent_list_runtime_backed() -> None:
    test_link_registry_creates_runtime_worker()
