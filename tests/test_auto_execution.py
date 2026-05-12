# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 50 — action-first policy gate."""

from __future__ import annotations

import pytest

from app.services.execution_policy import assess_interaction_risk, should_auto_execute


@pytest.mark.parametrize(
    ("intent", "risk", "expected"),
    [
        ("stuck_dev", "low", True),
        ("analysis", "low", True),
        ("stuck_dev", "high", False),
        ("analysis", "medium", False),
        ("general_chat", "low", False),
    ],
)
def test_should_auto_execute_matrix(intent: str, risk: str, expected: bool) -> None:
    assert should_auto_execute(intent, risk) is expected


def test_assess_risk_low_by_default() -> None:
    assert assess_interaction_risk("pytest failed on my branch") == "low"


def test_assess_risk_high_destructive() -> None:
    assert assess_interaction_risk("run rm -rf / on prod to fix") == "high"
