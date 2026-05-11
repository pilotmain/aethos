"""Autonomous goal planner (deterministic MVP)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from app.services.goal_orchestrator import GoalOrchestrator, parse_goal_intent


def test_parse_goal_build_app() -> None:
    p = parse_goal_intent("build a todo app")
    assert p is not None
    assert p["intent_type"] == "goal_build_app"


def test_execute_build_app_creates_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        parsed = parse_goal_intent("build a todo app")
        assert parsed
        orch = GoalOrchestrator()
        goal = orch.plan_sync(parsed, "build a todo app")
        out = orch.execute_goal_sync(goal, workspace_root=tmp, owner_user_id="u1")
        assert out.get("ok") is True
        assert (Path(tmp) / "todo-app" / "index.html").is_file()


def test_self_healing_retry_delay_increases() -> None:
    from app.services.self_healing import RetryConfig, RetryStrategy, retry_delay_seconds

    cfg = RetryConfig(max_attempts=3, base_delay=1.0, strategy=RetryStrategy.EXPONENTIAL, backoff_factor=2.0)
    assert retry_delay_seconds(0, cfg) == 0.0
    assert retry_delay_seconds(1, cfg) == 1.0
    assert retry_delay_seconds(2, cfg) == 2.0
