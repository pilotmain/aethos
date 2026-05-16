# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_brain_routing_confidence import test_brain_confidence_from_truth, test_brain_panel_has_routing_confidence


def test_e2e_brain_routing_confidence_flow() -> None:
    test_brain_panel_has_routing_confidence()
    test_brain_confidence_from_truth()
