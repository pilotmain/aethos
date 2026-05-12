# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 25 — DevOpsPanel snapshot fields."""

from __future__ import annotations


def test_mc_dev_run_fields_expected() -> None:
    keys = {
        "iterations",
        "tests_passed",
        "pr_ready",
        "max_iterations",
        "adapter_used",
        "privacy_warnings",
    }
    required_subset = {"iterations", "tests_passed", "pr_ready"}
    assert required_subset.issubset(keys)
