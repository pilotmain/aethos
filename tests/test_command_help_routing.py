from app.services.legacy_behavior_utils import build_response, Context
from app.services.intent_classifier import is_command_question
from app.services.command_help import format_command_help_response


def test_is_command_question_commands() -> None:
    assert is_command_question("What are the commands you understand?") is True
    assert is_command_question("What commands are there") is True


def test_is_command_not_helpful() -> None:
    assert is_command_question("this was helpful, thanks") is False


def test_format_command_has_nexa_next_workflows() -> None:
    body = format_command_help_response()
    assert "Nexa" in body
    assert "Mission Control" in body or "development" in body.lower()
    assert "/agents" not in body
    assert "@dev" not in body
    assert "Command Center" not in body


def test_build_response_command_overrides_projection() -> None:
    ctx = Context("u1", [], [], memory={})
    out = build_response(
        "List commands I can use",
        "capability_question",
        ctx,
        plan_result=None,
    )
    assert "Active agents right now" not in out
    assert "Command Center" not in out
    assert "mission" in out.lower() or "deliverable" in out.lower()
