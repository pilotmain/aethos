"""Phase 56 — confidence gate before auto dev execution."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_medium_confidence_returns_confirm_when_flag_enabled(
    monkeypatch: pytest.MonkeyPatch, nexa_runtime_clean
) -> None:
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
        "app.services.gateway.runtime.get_settings",
        lambda: SimpleNamespace(nexa_execution_confirm_medium=True),
    )

    gctx = GatewayContext(user_id="u_med", channel="web", extras={})
    # Short text, no error keywords, no memory → "medium" confidence.
    out = NexaGateway()._maybe_auto_dev_investigation(gctx, "fix it", db=nexa_runtime_clean)
    assert out is not None
    assert out.get("intent") == "execution_confirm"
    assert "yes, investigate" in (out.get("text") or "").lower()


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_medium_confidence_can_autorun_when_confirm_disabled(
    monkeypatch: pytest.MonkeyPatch, nexa_runtime_clean
) -> None:
    calls: list[dict] = []

    def _fake_run(db, uid, wid, goal, **kw):
        calls.append({"goal": goal, "on_progress": kw.get("on_progress")})
        return {"ok": True, "run_id": "r56", "tests_passed": True}

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
        "app.services.gateway.runtime.get_settings",
        lambda: SimpleNamespace(nexa_execution_confirm_medium=False),
    )
    monkeypatch.setattr(
        "app.services.execution_trigger.should_auto_execute_dev",
        lambda *a, **k: True,
    )
    monkeypatch.setattr("app.services.dev_runtime.service.run_dev_mission", _fake_run)
    monkeypatch.setattr(
        "app.services.dev_runtime.run_dev_gateway.format_dev_run_summary",
        lambda res: "ok",
    )

    gctx = GatewayContext(user_id="u_autorun", channel="web", extras={})
    out = NexaGateway()._maybe_auto_dev_investigation(gctx, "fix it", db=nexa_runtime_clean)
    assert out is not None
    assert out.get("intent") == "dev_mission"
    assert calls and calls[0]["goal"] == "fix it"


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_gateway_passes_on_dev_progress_to_run_dev_mission(
    monkeypatch: pytest.MonkeyPatch, nexa_runtime_clean
) -> None:
    sent: list = []

    def _fake_run(db, uid, wid, goal, **kw):
        sent.append(kw.get("on_progress"))
        return {"ok": True, "run_id": "r57"}

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
        "app.services.gateway.runtime.get_settings",
        lambda: SimpleNamespace(nexa_execution_confirm_medium=False),
    )
    monkeypatch.setattr(
        "app.services.execution_trigger.should_auto_execute_dev",
        lambda *a, **k: True,
    )
    monkeypatch.setattr("app.services.dev_runtime.service.run_dev_mission", _fake_run)
    monkeypatch.setattr(
        "app.services.dev_runtime.run_dev_gateway.format_dev_run_summary",
        lambda res: "done",
    )

    def tick(msg: str) -> None:
        pass

    gctx = GatewayContext(user_id="u_hook", channel="telegram", extras={"on_dev_progress": tick})
    out = NexaGateway()._maybe_auto_dev_investigation(
        gctx, "pytest fails on import with ModuleNotFoundError", db=nexa_runtime_clean
    )
    assert out is not None
    assert sent == [tick]
