# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 25 — PR readiness gate."""

from __future__ import annotations

from app.services.dev_runtime.pr import is_pr_ready


def test_pr_not_ready_when_tests_fail() -> None:
    assert (
        is_pr_ready(
            {
                "tests_passed": False,
                "changed_files_end": ["a.py"],
                "has_runtime_errors": False,
            }
        )
        is False
    )


def test_pr_ready_when_clean() -> None:
    assert (
        is_pr_ready(
            {
                "tests_passed": True,
                "changed_files_end": ["a.py"],
                "has_runtime_errors": False,
            }
        )
        is True
    )


def test_pr_not_ready_without_files() -> None:
    assert (
        is_pr_ready(
            {
                "tests_passed": True,
                "changed_files_end": [],
                "has_runtime_errors": False,
            }
        )
        is False
    )
