# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_worker_deliverable_persistence import test_deliverable_survives_after_output


def test_e2e_deliverable_visibility() -> None:
    test_deliverable_survives_after_output()
