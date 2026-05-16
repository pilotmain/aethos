# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_runtime_worker_clarity import test_runtime_workers_view_shape, test_truth_includes_runtime_workers


def test_e2e_runtime_worker_visibility() -> None:
    test_runtime_workers_view_shape()
    test_truth_includes_runtime_workers()
