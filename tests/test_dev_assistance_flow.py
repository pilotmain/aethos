"""Phase 49 — development blockage intent and composer hooks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.response_composer import ResponseContext, compose_unstick_response


def _minimal_ctx(*, intent: str, msg: str) -> ResponseContext:
    return ResponseContext(
        user_message=msg,
        intent=intent,
        behavior="unstick",
        has_active_plan=False,
        focus_task=None,
        selected_tasks=[],
        deferred_lines=[],
        planning_style="gentle",
        detected_state=None,
        voice_style="direct",
        focus_attempts=0,
        is_stuck_loop=False,
        user_preferences={},
        memory_enabled=True,
        memory_note_count=0,
        conversation_summary=None,
        active_topic=None,
        active_topic_confidence=0.5,
        manual_topic_override=False,
        recent_messages=[],
        routing_agent_key="nexa",
        response_kind=None,
        prompt_budget_tier=2,
    )


def test_compose_unstick_appends_stuck_dev_extra_to_prompt(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_run(ctx: ResponseContext, strategy_body: str):
        captured["body"] = strategy_body
        return {
            "message": "ok",
            "should_ask_followup": False,
            "followup_question": None,
            "suggested_microstep": None,
            "next_steps": None,
        }

    monkeypatch.setattr("app.services.response_composer.use_real_llm", lambda: True)
    monkeypatch.setattr("app.services.response_composer._run_strategy", fake_run)

    compose_unstick_response(_minimal_ctx(intent="general_chat", msg="x"))
    assert "stuck_dev" not in captured.get("body", "")

    compose_unstick_response(_minimal_ctx(intent="stuck_dev", msg="pytest fails"))
    assert "stuck_dev" in captured["body"].lower()
    assert "next_steps" in captured["body"].lower() and "null" in captured["body"].lower()
