"""
Phase 54A — deep memory in dev + mission planning, workspace guidance, regression cases.
"""

from __future__ import annotations

import pytest

from app.models.dev_runtime import NexaDevWorkspace
from app.services.dev_runtime.planner import build_dev_plan
from app.services.execution_policy import should_prompt_for_dev_workspace_help
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway
from app.services.token_economy.context_builder import build_minimal_provider_context


def test_planner_marks_memory_step() -> None:
    w = NexaDevWorkspace(
        id="w1",
        user_id="u",
        name="n",
        repo_path="/tmp",
        status="ready",
    )
    plan = build_dev_plan("fix it", w, memory_notes="Stack: EKS, Mongo, Spring, OIDC")
    assert any(s.get("memory_notes_excerpt") for s in plan if s.get("type") == "analyze")


def test_provider_context_accepts_turn_memory() -> None:
    ctx, _e, s = build_minimal_provider_context(
        task="t", turn_memory_summary="User stack: Spring + Mongo"
    )
    assert "turn_memory_summary" in ctx
    assert s.get("turn_memory_summary_chars", 0) > 0


def test_should_prompt_for_dev_workspace_help() -> None:
    assert should_prompt_for_dev_workspace_help("stuck_dev", "low", "tests fail on CI") is True
    assert should_prompt_for_dev_workspace_help("stuck_dev", "high", "ok") is False
    assert should_prompt_for_dev_workspace_help("general_chat", "low", "hi") is False


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_zero_workspace_guidance(monkeypatch: pytest.MonkeyPatch, nexa_runtime_clean) -> None:
    monkeypatch.setattr(
        "app.services.dev_runtime.workspace.list_workspaces",
        lambda db, uid: [],
    )
    monkeypatch.setattr(
        "app.services.conversation_context_service.get_or_create_context",
        lambda *a, **k: object(),
    )
    monkeypatch.setattr(
        "app.services.conversation_context_service.build_context_snapshot",
        lambda *a, **k: {},
    )
    monkeypatch.setattr("app.services.intent_classifier.get_intent", lambda *a, **k: "stuck_dev")
    monkeypatch.setattr("app.services.execution_policy.assess_interaction_risk", lambda t: "low")

    gctx = GatewayContext(user_id="u0", channel="web", extras={})
    out = NexaGateway()._maybe_auto_dev_investigation(gctx, "Spring Boot Mongo OIDC auth fails in EKS", db=nexa_runtime_clean)
    assert out is not None
    assert "workspace" in out["text"].lower() or "mission control" in out["text"].lower()


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_multi_workspace_lists_options(monkeypatch: pytest.MonkeyPatch, nexa_runtime_clean) -> None:
    w1 = type("W", (), {"id": "a", "name": "nexa-next"})()
    w2 = type("W", (), {"id": "b", "name": "backend-api"})()
    monkeypatch.setattr(
        "app.services.dev_runtime.workspace.list_workspaces",
        lambda db, uid: [w1, w2],
    )
    monkeypatch.setattr(
        "app.services.conversation_context_service.get_or_create_context",
        lambda *a, **k: object(),
    )
    monkeypatch.setattr(
        "app.services.conversation_context_service.build_context_snapshot",
        lambda *a, **k: {},
    )
    monkeypatch.setattr("app.services.intent_classifier.get_intent", lambda *a, **k: "stuck_dev")
    monkeypatch.setattr("app.services.execution_policy.assess_interaction_risk", lambda t: "low")

    gctx = GatewayContext(user_id="um", channel="web", extras={})
    out = NexaGateway()._maybe_auto_dev_investigation(gctx, "pytest import error in my project", db=nexa_runtime_clean)
    assert out is not None
    assert "which workspace" in out["text"].lower()
    assert "nexa-next" in out["text"]


def test_destructive_text_skips_workspace_prompts(monkeypatch: pytest.MonkeyPatch) -> None:
    """High-risk phrasing should not surface dev workspace UX (fail closed to chat fall-through)."""
    from app.core.db import SessionLocal

    with SessionLocal() as db:
        monkeypatch.setattr(
            "app.services.dev_runtime.workspace.list_workspaces",
            lambda d, u: [],
        )
        monkeypatch.setattr(
            "app.services.conversation_context_service.get_or_create_context",
            lambda *a, **k: object(),
        )
        monkeypatch.setattr(
            "app.services.conversation_context_service.build_context_snapshot",
            lambda *a, **k: {},
        )
        monkeypatch.setattr("app.services.intent_classifier.get_intent", lambda *a, **k: "stuck_dev")
        # risk from real assessor
        gctx = GatewayContext(user_id="ud", channel="web", extras={})
        out = NexaGateway()._maybe_auto_dev_investigation(
            gctx, "rm -rf / and fix prod", db=db
        )
        assert out is None
