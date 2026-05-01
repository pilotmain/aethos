"""Active agent projection (command-center visibility)."""

from app.services.agent_router import (
    format_active_agent_projection,
    infer_active_agents_from_text,
    should_emit_active_agent_projection,
)


def test_infer_meta_question_returns_strategy_and_developer() -> None:
    agents = infer_active_agents_from_text("Which agent is handling what?")
    assert agents == ["strategy", "developer", "ops"]


def test_infer_keywords_dev_and_qa() -> None:
    agents = infer_active_agents_from_text("Fix the API bug and add a pytest")
    assert "developer" in agents
    assert "qa" in agents


def test_infer_default_strategy() -> None:
    agents = infer_active_agents_from_text("hello there")
    assert agents == ["strategy"]


def test_format_projection_order() -> None:
    out = format_active_agent_projection(
        ["strategy", "developer", "ops"],
        active_topic="Nexa",
    )
    assert "Active topic: Nexa" in out
    assert "Active agents right now:" in out
    assert "Strategy →" in out
    assert "Developer →" in out
    assert "Ops →" in out
    assert out.count("—") == 3


def test_format_projection_with_topic() -> None:
    out2 = format_active_agent_projection(
        ["strategy", "developer", "ops"]
    )
    assert "Active agents right now:" in out2
    assert "Ops →" in out2


def test_should_emit_capability() -> None:
    assert should_emit_active_agent_projection("capability_question", "can you design?") is False


def test_should_emit_brain_dump_false() -> None:
    assert should_emit_active_agent_projection("brain_dump", "which agent?") is False


def test_should_emit_agent_word() -> None:
    assert should_emit_active_agent_projection("general_chat", "what is the dev agent for?") is False
    assert should_emit_active_agent_projection("general_chat", "which agent handles the dev work?") is True


def test_should_emit_meta_without_agents_token() -> None:
    assert should_emit_active_agent_projection("general_chat", "which agent is handling what?") is True
