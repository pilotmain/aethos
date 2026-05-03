"""Phase 53 — auto dev execution policy and gateway copy."""

from __future__ import annotations

import pytest

from app.services.execution_policy import (
    should_auto_execute_dev_turn,
    should_auto_run_dev_task,
    user_said_do_not_run,
)
from app.services.identity.scrub import gateway_identity_needs_scrub


def test_should_auto_execute_dev_turn_matches_run_dev_task() -> None:
    assert should_auto_execute_dev_turn("stuck_dev", "low", 1, "fix tests") == should_auto_run_dev_task(
        "stuck_dev", "low", 1, "fix tests"
    )


def test_user_said_do_not_run_anything() -> None:
    assert user_said_do_not_run("do not run anything, theory only")


def test_auto_dev_intro_has_no_rest_or_legacy_phrases() -> None:
    intro = "I'll investigate this against your workspace now.\n\n"
    low = intro.lower()
    assert "post /api" not in low
    assert "tell cursor" not in low
    assert "development agent" not in low
    assert "@dev" not in intro
    assert not gateway_identity_needs_scrub(intro)


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_maybe_auto_dev_prepends_intro(monkeypatch: pytest.MonkeyPatch, nexa_runtime_clean) -> None:
    from app.services.gateway.context import GatewayContext
    from app.services.gateway.runtime import NexaGateway

    calls: list[tuple] = []

    def _fake_run(db, uid, wid, goal, **kw):
        calls.append((goal, kw.get("memory_notes")))
        return {"ok": True, "run_id": "r1", "iterations": 1, "tests_passed": True, "adapter_used": "stub"}

    monkeypatch.setattr(
        "app.services.dev_runtime.workspace.list_workspaces",
        lambda db, uid: [type("W", (), {"id": "ws1"})()],
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
    monkeypatch.setattr(
        "app.services.execution_policy.should_auto_execute_dev_turn",
        lambda *a, **k: True,
    )
    monkeypatch.setattr("app.services.dev_runtime.service.run_dev_mission", _fake_run)
    monkeypatch.setattr(
        "app.services.dev_runtime.run_dev_gateway.format_dev_run_summary",
        lambda res: "Done.",
    )

    gctx = GatewayContext(user_id="u_intro", channel="web", extras={"via_gateway": True})
    gctx.memory = {"summary": "Stack: EKS, Mongo.", "used": True}
    out = NexaGateway()._maybe_auto_dev_investigation(gctx, "auth fails", db=nexa_runtime_clean)
    assert out is not None
    assert out["text"].startswith("I'll investigate this against your workspace")
    assert calls
    assert "EKS" in (calls[0][1] or "") or "EKS" in (calls[0][0] or "")
