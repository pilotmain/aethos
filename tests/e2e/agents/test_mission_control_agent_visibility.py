# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_agent_runtime_traceability import test_truth_includes_agent_visibility


def test_e2e_mc_agent_visibility() -> None:
    test_truth_includes_agent_visibility()
