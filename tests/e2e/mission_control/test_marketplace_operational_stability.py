# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_marketplace_operational_stability import test_marketplace_stability_trust


def test_e2e_marketplace_operational_stability() -> None:
    test_marketplace_stability_trust()
