# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_governance_operational_readability import test_governance_timeline_kinds


def test_e2e_governance_readability_flow() -> None:
    test_governance_timeline_kinds()
