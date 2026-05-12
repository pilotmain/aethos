"""Execution planner NL extensions (file-based plans only)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.execution_planner import (
    acquire_plan_slot,
    build_multi_step_specs,
    parse_extended_build_intent,
    release_plan_slot,
)
from app.services.goal_orchestrator import GoalOrchestrator, parse_goal_intent


def test_parse_extended_requires_flag() -> None:
    with patch("app.services.goal_orchestrator.get_settings") as m:
        m.return_value = MagicMock(nexa_execution_planner_enabled=False)
        assert parse_goal_intent("build a todo app with database") is None


def test_parse_extended_build_multi() -> None:
    with patch("app.services.goal_orchestrator.get_settings") as m:
        m.return_value = MagicMock(nexa_execution_planner_enabled=True)
        p = parse_goal_intent("build a todo app with database backend")
        assert p is not None
        assert p["intent_type"] == "goal_build_multi"
        assert p["hints"].get("want_db") is True


def test_build_multi_step_specs_db() -> None:
    specs = build_multi_step_specs({"want_db": True}, "todo app")
    assert len(specs) == 2
    assert all(s["step_kind"] == "batch_files" for s in specs)


def test_plan_slot_acquire_release() -> None:
    assert acquire_plan_slot("u1", 2) is True
    assert acquire_plan_slot("u1", 2) is True
    assert acquire_plan_slot("u1", 2) is False
    release_plan_slot("u1")
    assert acquire_plan_slot("u1", 2) is True
    release_plan_slot("u1")
    release_plan_slot("u1")


def test_execute_multi_writes_backend(tmp_path) -> None:
    with patch("app.services.goal_orchestrator.get_settings") as m:
        m.return_value = MagicMock(nexa_execution_planner_enabled=True)
        parsed = parse_goal_intent("build a todo app with sqlite backend")
        assert parsed and parsed["intent_type"] == "goal_build_multi"
    orch = GoalOrchestrator()
    goal = orch.plan_sync(parsed, "build a todo app with sqlite backend")
    out = orch.execute_goal_sync(goal, workspace_root=str(tmp_path), owner_user_id="u1")
    assert out.get("ok") is True
    assert list(tmp_path.rglob("server.js")), "expected backend/server.js"
