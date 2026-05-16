# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_provider_reliability_visibility import test_provider_reliability_summary


def test_e2e_provider_reliability_flow() -> None:
    test_provider_reliability_summary()
