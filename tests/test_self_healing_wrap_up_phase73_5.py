# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 73.5 — wrap-up tests for the self-healing loop.

Covers the two behavioral additions:

* :func:`AgentExecutor.execute` calls
  :meth:`RecoveryHandler.reset_recovery_attempts` on a successful task so a
  flapping-then-recovered agent gets its quota back and isn't escalated on the
  next hiccup. The hook is wrapped in ``try/except`` and must not break the
  executor when self-healing is disabled or the recovery handler raises.
* The hook is a no-op when the counter is already at zero (no spurious
  registry writes / log spam).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.sub_agent_autoqueue_guard import reset_autoqueue_counts_for_tests
from app.services.sub_agent_executor import AgentExecutor
from app.services.sub_agent_rate_limit import reset_rate_limiter_for_tests
from app.services.sub_agent_registry import AgentRegistry, AgentStatus, SubAgent


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    reset_rate_limiter_for_tests()
    reset_autoqueue_counts_for_tests()
    AgentRegistry.reset()
    # Phase 73 tests inject fakes into the recovery-handler singleton; reset it
    # so the executor sees a fresh handler bound to the real AgentRegistry.
    import app.services.agent.recovery as _recovery_mod

    monkeypatch.setattr(_recovery_mod, "_recovery_handler", None, raising=False)
    yield
    reset_rate_limiter_for_tests()
    reset_autoqueue_counts_for_tests()
    AgentRegistry.reset()


class _Settings:
    nexa_agent_orchestration_enabled = True
    nexa_agent_orchestration_autoqueue = False
    nexa_host_executor_enabled = True
    nexa_host_executor_chain_enabled = True
    nexa_nl_to_chain_enabled = True


def _seed_agent_with_attempts(attempts: int) -> SubAgent:
    """Seed a git-domain agent into the singleton registry with prior recovery state."""
    agent = SubAgent(
        id="a-heal",
        name="git-agent",
        domain="git",
        capabilities=["commit", "push"],
        parent_chat_id="chat-heal",
        status=AgentStatus.IDLE,
        metadata={
            "recovery_attempts": attempts,
            "last_recovery_strategy": "state_reset",
            "last_recovery_at": 12345.6,
        },
    )
    reg = AgentRegistry()
    reg._agents[agent.id] = agent  # type: ignore[attr-defined]
    return agent


def test_executor_clears_recovery_attempts_on_successful_task() -> None:
    """A clean execute() call must wipe the prior failure quota."""
    agent = _seed_agent_with_attempts(2)
    executor = AgentExecutor()
    with patch("app.services.sub_agent_executor.get_settings", return_value=_Settings()):
        out = executor.execute(
            agent,
            "nonsense that matches nothing",  # returns help text via success path
            "chat-heal",
            db=MagicMock(),
            user_id="u1",
        )
    assert isinstance(out, str)

    refreshed = AgentRegistry().get_agent(agent.id)
    assert refreshed is not None
    md = refreshed.metadata or {}
    assert "recovery_attempts" not in md
    assert "last_recovery_strategy" not in md
    assert "last_recovery_at" not in md


def test_executor_idempotent_when_attempts_already_zero() -> None:
    """No-op path: attempts == 0 should not spuriously touch the registry row.

    We can't easily assert "no write" without a deeper hook, but the call path
    should still complete cleanly and leave metadata untouched (no keys added).
    """
    agent = SubAgent(
        id="a-heal-zero",
        name="git-agent",
        domain="git",
        capabilities=["commit"],
        parent_chat_id="chat-heal",
        status=AgentStatus.IDLE,
        metadata={"unrelated": "value"},
    )
    AgentRegistry()._agents[agent.id] = agent  # type: ignore[attr-defined]

    executor = AgentExecutor()
    with patch("app.services.sub_agent_executor.get_settings", return_value=_Settings()):
        executor.execute(
            agent,
            "nonsense",
            "chat-heal",
            db=MagicMock(),
            user_id="u1",
        )

    refreshed = AgentRegistry().get_agent(agent.id)
    assert refreshed is not None
    md = refreshed.metadata or {}
    assert "recovery_attempts" not in md  # not added
    assert md.get("unrelated") == "value"  # untouched


def test_executor_swallows_recovery_handler_failure() -> None:
    """If the reset hook raises, the executor must not bubble the error."""
    agent = _seed_agent_with_attempts(1)

    class _BoomHandler:
        def reset_recovery_attempts(self, _agent_id: str) -> None:
            raise RuntimeError("recovery handler unavailable")

    executor = AgentExecutor()
    with patch("app.services.sub_agent_executor.get_settings", return_value=_Settings()), patch(
        "app.services.agent.recovery.get_recovery_handler",
        return_value=_BoomHandler(),
    ):
        out = executor.execute(
            agent,
            "nonsense",
            "chat-heal",
            db=MagicMock(),
            user_id="u1",
        )
    assert isinstance(out, str)
    # The reset path failed, so attempts should still be present (we didn't
    # silently mutate state on the failure path).
    refreshed = AgentRegistry().get_agent(agent.id)
    assert refreshed is not None
    assert int((refreshed.metadata or {}).get("recovery_attempts", 0) or 0) == 1


def test_executor_does_not_clear_on_failed_task() -> None:
    """An exception inside _dispatch must skip the auto-clear (failure path)."""
    agent = _seed_agent_with_attempts(2)

    executor = AgentExecutor()
    with patch("app.services.sub_agent_executor.get_settings", return_value=_Settings()), patch.object(
        AgentExecutor,
        "_dispatch",
        side_effect=RuntimeError("boom"),
    ):
        out = executor.execute(
            agent,
            "anything",
            "chat-heal",
            db=MagicMock(),
            user_id="u1",
        )
    assert "Execution failed" in out  # wrapped error message from execute()

    refreshed = AgentRegistry().get_agent(agent.id)
    assert refreshed is not None
    assert int((refreshed.metadata or {}).get("recovery_attempts", 0) or 0) == 2


# Silence unused-import warnings for SimpleNamespace if a future refactor drops it.
_ = SimpleNamespace
