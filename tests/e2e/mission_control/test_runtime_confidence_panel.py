# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_runtime_confidence_summary import test_runtime_confidence_shape


def test_e2e_runtime_confidence_panel() -> None:
    test_runtime_confidence_shape()
