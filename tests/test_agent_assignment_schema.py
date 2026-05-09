"""POST /agent-assignments payload coercion (legacy ``task`` / ``agent_id``)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.schemas.agent_organization import AgentAssignmentCreate
from app.services.custom_agents import normalize_agent_key
from app.services.sub_agent_registry import AgentRegistry


class _OrchOn:
    nexa_agent_orchestration_enabled = True
    nexa_agent_max_per_chat = 20
    nexa_agent_idle_timeout_seconds = 3600


def test_assignment_create_coerces_agent_id_and_task() -> None:
    AgentRegistry.reset()
    with patch("app.services.sub_agent_registry.get_settings", return_value=_OrchOn()):
        reg = AgentRegistry()
        ag = reg.spawn_agent("My-Agent", "qa", "web:tester:default")
        assert ag is not None

    p = AgentAssignmentCreate(agent_id=ag.id, task="Review the repo")
    assert p.assigned_to_handle == "my_agent"
    assert p.title == "Review the repo"
    assert "repo" in p.description.lower()


def test_assignment_create_rejects_unknown_agent_id() -> None:
    AgentRegistry.reset()
    with pytest.raises(ValidationError):
        AgentAssignmentCreate(agent_id="not-real-id", task="x")


def test_assignment_create_accepts_explicit_handle() -> None:
    p = AgentAssignmentCreate(assigned_to_handle="research-analyst", title="t", description="d")
    assert p.assigned_to_handle == normalize_agent_key("research-analyst")


def test_assignment_create_agent_handle_alias() -> None:
    p = AgentAssignmentCreate(agent_handle="Git-Agent", task="deploy")
    assert p.assigned_to_handle == "git_agent"
    assert p.title == "deploy"
