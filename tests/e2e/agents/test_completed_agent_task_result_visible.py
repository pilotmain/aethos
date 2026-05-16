# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_agent_output_persistence import test_output_persisted


def test_e2e_completed_result_visible() -> None:
    test_output_persisted()
