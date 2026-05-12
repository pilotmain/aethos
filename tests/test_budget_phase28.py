# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 28 — per-member token budgets (SQLite tracker + hooks)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.budget.hooks import (
    estimate_tokens_from_messages,
    estimate_tokens_from_text,
)
from app.services.budget.models import BudgetStatus, UsageType
from app.services.budget.tracker import BudgetTracker
from app.services.llm.base import Message


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "t_budget.db"


def test_estimate_tokens_from_text() -> None:
    assert estimate_tokens_from_text("") == 0
    s = "x" * 400
    assert estimate_tokens_from_text(s) >= 100


def test_estimate_tokens_from_messages() -> None:
    m = [Message(role="user", content="hello " * 40)]
    assert estimate_tokens_from_messages(m) >= 10


def test_tracker_create_record_adjust(db_path: Path) -> None:
    tr = BudgetTracker(db_path=db_path)
    b = tr.get_or_create_budget("m1", monthly_limit=1000)
    assert b.monthly_limit == 1000
    assert b.current_usage == 0

    r = tr.record_usage("m1", 100, UsageType.AGENT_TASK, description="task")
    assert r is not None
    b2 = tr.get_or_create_budget("m1")
    assert b2.current_usage == 100

    tr.adjust_budget("m1", 50, "grant")
    b3 = tr.get_or_create_budget("m1")
    assert b3.current_usage == 50

    tr.set_budget_limit("m1", 500)
    tr.record_usage("m1", 20, UsageType.LLM_CALL)
    b4 = tr.get_or_create_budget("m1")
    assert b4.current_usage == 70


def test_tracker_blocks_when_exhausted(db_path: Path) -> None:
    tr = BudgetTracker(db_path=db_path)
    tr.get_or_create_budget("x", monthly_limit=100)
    tr.record_usage("x", 100, UsageType.LLM_CALL)
    b = tr.get_or_create_budget("x")
    assert b.status == BudgetStatus.PAUSED
    assert not b.can_execute(1)
    assert tr.record_usage("x", 1, UsageType.LLM_CALL) is None


def test_override_skips_meter_increment(db_path: Path) -> None:
    tr = BudgetTracker(db_path=db_path)
    tr.get_or_create_budget("ov", monthly_limit=10)
    tr.record_usage("ov", 10, UsageType.LLM_CALL)
    assert tr.get_or_create_budget("ov").status == BudgetStatus.PAUSED
    tr.set_override("ov", True)
    tr.record_usage("ov", 5000, UsageType.LLM_CALL)
    assert tr.get_or_create_budget("ov").current_usage == 10


def test_get_usage_filters_days(db_path: Path) -> None:
    tr = BudgetTracker(db_path=db_path)
    tr.get_or_create_budget("z", monthly_limit=99999)
    tr.record_usage("z", 5, UsageType.LLM_CALL)
    rows = tr.get_usage("z", days=30)
    assert len(rows) >= 1
    assert rows[0].tokens == 5


def test_team_summary(db_path: Path) -> None:
    tr = BudgetTracker(db_path=db_path)
    tr.get_or_create_budget("a", monthly_limit=100)
    tr.get_or_create_budget("b", monthly_limit=100)
    tr.record_usage("a", 30, UsageType.AGENT_TASK)
    s = tr.get_team_summary(["a", "b"])
    assert s["team_total_used"] == 30
    assert s["team_total_limit"] == 200
