"""Topic authority: explicit user instructions over inferred memory."""

from app.services.conversation_context_service import (
    apply_topic_intent_to_context,
    detect_topic_override,
    short_reply_for_topic_intent,
)
from app.models.conversation_context import ConversationContext


def test_detect_combined_forget_and_switch() -> None:
    o = detect_topic_override("Forget LifeOS now let's talk about agents")
    assert o == ("set", "agents")


def test_detect_switch_topic_to() -> None:
    o = detect_topic_override("Switch topic to billing")
    assert o == ("set", "billing")


def test_detect_standalone_forget_clears() -> None:
    o = detect_topic_override("forget lifeos")
    assert o == ("clear", "")


def test_detect_does_not_trigger_on_slash() -> None:
    assert detect_topic_override("/forget something") is None


def test_short_reply_set() -> None:
    text = short_reply_for_topic_intent(("set", "agents"))
    assert "agents" in text
    assert text.startswith("Got it — switching context to:")


def test_apply_topic_set_marks_override() -> None:
    ctx = ConversationContext(
        user_id="u1",
        recent_messages_json="[]",
        active_topic="old",
        active_topic_confidence=0.5,
        manual_topic_override=False,
    )
    o = apply_topic_intent_to_context(ctx, "Switch topic to agents")
    assert o is not None
    assert ctx.active_topic == "agents"
    assert ctx.manual_topic_override is True
    assert (ctx.active_topic_confidence or 0) >= 0.99
