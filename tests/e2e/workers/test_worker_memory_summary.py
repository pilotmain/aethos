# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from tests.test_worker_operational_summaries import test_worker_summary_has_specialization


def test_e2e_memory_summary() -> None:
    test_worker_summary_has_specialization()
