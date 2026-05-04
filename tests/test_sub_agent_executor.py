"""Week 4 Phase 3 — sub_agent_executor (sync)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.sub_agent_executor import AgentExecutor
from app.services.sub_agent_registry import AgentRegistry, AgentStatus, SubAgent


class _S:
    nexa_agent_orchestration_enabled = True
    nexa_agent_orchestration_autoqueue = False
    nexa_host_executor_enabled = True
    nexa_host_executor_chain_enabled = True
    nexa_nl_to_chain_enabled = True


class _Auto:
    nexa_agent_orchestration_enabled = True
    nexa_agent_orchestration_autoqueue = True
    nexa_host_executor_enabled = True
    nexa_host_executor_chain_enabled = True
    nexa_nl_to_chain_enabled = True


@pytest.fixture
def executor() -> AgentExecutor:
    return AgentExecutor()


@pytest.fixture
def registry() -> AgentRegistry:
    AgentRegistry.reset()
    return AgentRegistry()


def _git_agent() -> SubAgent:
    return SubAgent(
        id="a1",
        name="git-agent",
        domain="git",
        capabilities=["commit", "push"],
        parent_chat_id="chat123",
    )


def test_git_help_text(executor: AgentExecutor) -> None:
    a = _git_agent()
    with patch("app.services.sub_agent_executor.get_settings", return_value=_S()):
        out = executor.execute(
            a,
            "nonsense that matches nothing",
            "chat123",
            db=MagicMock(),
            user_id="u1",
        )
    assert "Git sub-agent" in out or "try" in out.lower()


def test_queue_chain_needs_db(executor: AgentExecutor) -> None:
    a = _git_agent()
    with (
        patch("app.services.sub_agent_executor.get_settings", return_value=_S()),
        patch("app.services.sub_agent_executor.try_infer_readme_push_chain_nl") as inf,
    ):
        inf.return_value = {
            "host_action": "chain",
            "actions": [{"host_action": "file_write", "relative_path": "x", "content": "y"}],
        }
        out = executor.execute(
            a,
            "add README and push",
            "chat123",
            db=None,
            user_id="u1",
        )
    assert "session" in out.lower() or "database" in out.lower()


def test_queue_chain_with_mock_enqueue(registry: AgentRegistry) -> None:
    a = _git_agent()
    mock_db = MagicMock()
    with (
        patch("app.services.sub_agent_executor.get_settings", return_value=_S()),
        patch("app.services.sub_agent_executor.try_infer_readme_push_chain_nl") as inf,
        patch("app.services.sub_agent_executor._validate_enqueue_payload") as val,
        patch("app.services.sub_agent_executor.enqueue_host_job_from_validated_payload") as enq,
    ):
        inf.return_value = {
            "host_action": "chain",
            "actions": [{"host_action": "file_write", "relative_path": "r.md", "content": "c"}],
        }
        val.return_value = inf.return_value
        enq.return_value = SimpleNamespace(id=99)
        out = AgentExecutor().execute(
            a,
            "add a README and push",
            "chat123",
            db=mock_db,
            user_id="u1",
            web_session_id="default",
        )
    assert "99" in out
    assert "job" in out.lower()


def test_autoqueue_runs_execute_payload(executor: AgentExecutor) -> None:
    a = _git_agent()
    with (
        patch("app.services.sub_agent_executor.get_settings", return_value=_Auto()),
        patch("app.services.sub_agent_executor.try_infer_readme_push_chain_nl") as inf,
        patch("app.services.sub_agent_executor._validate_enqueue_payload") as val,
        patch("app.services.sub_agent_executor.execute_payload", return_value="ok-out") as ex,
    ):
        pl = {
            "host_action": "chain",
            "actions": [{"host_action": "file_write", "relative_path": "a", "content": "b"}],
        }
        inf.return_value = pl
        val.return_value = pl
        out = executor.execute(
            a,
            "add a README and push",
            "chat123",
            db=MagicMock(),
            user_id="u1",
        )
    assert "ok-out" in out
    ex.assert_called_once()


def test_vercel_list_queues(executor: AgentExecutor) -> None:
    a = SubAgent(
        id="v1",
        name="v",
        domain="vercel",
        capabilities=["list"],
        parent_chat_id="c",
    )
    mock_db = MagicMock()
    with (
        patch("app.services.sub_agent_executor.get_settings", return_value=_S()),
        patch("app.services.sub_agent_executor._validate_enqueue_payload") as val,
        patch("app.services.sub_agent_executor.enqueue_host_job_from_validated_payload") as enq,
    ):
        val.return_value = {"host_action": "vercel_projects_list"}
        enq.return_value = SimpleNamespace(id=7)
        out = executor.execute(a, "list my vercel projects", "c", db=mock_db, user_id="u2")
    assert "7" in out


def test_railway_placeholder(executor: AgentExecutor) -> None:
    a = SubAgent(
        id="r1",
        name="r",
        domain="railway",
        capabilities=[],
        parent_chat_id="c",
    )
    out = executor.execute(a, "deploy", "c", db=None, user_id="u1")
    assert "Railway" in out


def test_idle_after_execute(registry: AgentRegistry) -> None:
    reg = registry
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S()):
        ag = reg.spawn_agent("g", "git", "chat123")
        assert ag is not None
    with patch("app.services.sub_agent_executor.get_settings", return_value=_S()):
        AgentExecutor().execute(ag, "random xyz no match", "chat123", db=None, user_id="")
    assert reg.get_agent(ag.id) is not None
    assert reg.get_agent(ag.id).status == AgentStatus.IDLE
