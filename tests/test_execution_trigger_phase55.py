"""Phase 55 — execution trigger + decisive dev tone."""

from __future__ import annotations

from app.services.execution_policy import should_auto_execute_dev_turn
from app.services.execution_trigger import (
    should_auto_execute_dev,
    should_merge_phase50_assist,
    should_use_decisive_dev_tone,
)


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
