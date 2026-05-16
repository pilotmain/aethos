# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_operator_onboarding_visibility import test_onboarding_checks


def test_e2e_operator_onboarding_flow() -> None:
    test_onboarding_checks()
