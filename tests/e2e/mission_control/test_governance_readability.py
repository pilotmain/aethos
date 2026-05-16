# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_governance_timeline_visibility import test_governance_timeline_human_readable


def test_e2e_governance_readability() -> None:
    test_governance_timeline_human_readable()
