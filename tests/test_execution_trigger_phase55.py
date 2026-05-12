# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 55 — execution trigger + decisive dev tone."""

from __future__ import annotations

from app.services.execution_policy import should_auto_execute_dev_turn
from app.services.execution_trigger import (
    compute_execution_confidence,
    should_auto_execute_dev,
    should_execute_now,
    should_merge_phase50_assist,
    should_use_decisive_dev_tone,
)


def test_should_execute_now_matches_low_risk_single_ws() -> None:
    assert should_execute_now("stuck_dev", 1, "low", user_text="pytest fails on import") is True
    assert should_execute_now("stuck_dev", 0, "low", user_text="ok") is False
    assert should_execute_now("stuck_dev", 1, "high", user_text="ok") is False


def test_compute_execution_confidence_smoke() -> None:
    assert (
        compute_execution_confidence(
            "stuck_dev",
            "npm test failed with assertion error",
            memory_summary=None,
            workspace_count=1,
        )
        == "high"
    )
    assert compute_execution_confidence("brain_dump", "lots of stuff", memory_summary=None, workspace_count=1) == "low"


def test_should_auto_execute_dev_matches_policy_alias() -> None:
    assert should_auto_execute_dev("fix tests", "stuck_dev", workspace_count=1) == should_auto_execute_dev_turn(
        "stuck_dev", "low", 1, "fix tests"
    )


def test_decisive_tone_for_dev_intents() -> None:
    assert should_use_decisive_dev_tone("analysis") is True
    assert should_use_decisive_dev_tone("stuck_dev") is True
    assert should_use_decisive_dev_tone("brain_dump") is False


def test_phase50_assist_skipped_when_decisive() -> None:
    assert should_merge_phase50_assist("analysis") is False
    assert should_merge_phase50_assist("brain_dump") is True
