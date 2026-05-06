from app.services.legacy_behavior_utils import build_response, Context
from app.services.intent_classifier import is_command_question
from app.services.command_help import format_command_help_response
from app.services.system_identity.capabilities import is_capability_identity_question


def test_is_command_question_commands() -> None:
    assert is_command_question("What are the commands you understand?") is True
    assert is_command_question("What commands are there") is True


def test_is_command_not_helpful() -> None:
    assert is_command_question("this was helpful, thanks") is False


def test_format_command_help_is_aethos_branded() -> None:
    body = format_command_help_response()
    assert "AethOS" in body
    assert "Mission Control" in body or "development" in body.lower()
    assert "/agents" not in body
    assert "@dev" not in body
    assert "Command Center" not in body


def test_capability_identity_question_routes_to_narrative_not_slash_roster() -> None:
    assert is_capability_identity_question("What can you do?") is True
    assert is_capability_identity_question("what can you do with Rust") is False
    assert is_capability_identity_question("What are your capabilities?") is True


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


def test_build_response_what_can_you_do_uses_narrative_capability() -> None:
    ctx = Context("u1", [], [], memory={})
    out = build_response(
        "What can you do?",
        "general_chat",
        ctx,
        plan_result=None,
    )
    assert "I'm AethOS" in out
    assert "describe what you want" not in out
