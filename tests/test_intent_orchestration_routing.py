"""Orchestration / external infra intents — do not downgrade to local file path UX."""

from __future__ import annotations

from app.services.intent_classifier import (
    get_intent,
    looks_like_external_investigation,
    looks_like_orchestrate_system,
)
from app.services.local_file_intent import infer_local_file_request


def test_orchestrate_system_intent_triggers() -> None:
    assert looks_like_orchestrate_system("Check Mission Control and report what succeeded vs failed")
    assert get_intent("Act as orchestrator and summarize active work") == "orchestrate_system"


def test_external_investigation_intent_triggers() -> None:
    assert looks_like_external_investigation("Railway worker keeps crashing after deploy")
    assert get_intent("Why is my Railway service unhealthy") == "external_investigation"


def test_infer_local_file_skips_when_orchestrating() -> None:
    lf = infer_local_file_request(
        "Please check Mission Control and tell me what failed on Railway",
        default_relative_base=".",
    )
    assert lf.matched is False


def test_orchestrate_wins_over_external_when_both_cues() -> None:
    assert (
        get_intent("Mission Control says Railway failed — what happened?") == "orchestrate_system"
    )
