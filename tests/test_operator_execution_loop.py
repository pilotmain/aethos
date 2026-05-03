"""Operator execution loop — gateway wiring and provider selection."""

from __future__ import annotations

import uuid

import pytest

from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway
from app.services.operator_execution_loop import try_operator_execution


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_operator_loop_skipped_when_mode_off(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_execution_loop.get_settings",
        lambda: __import__("types").SimpleNamespace(nexa_operator_mode=False),
    )
    uid = f"op_{uuid.uuid4().hex[:8]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    r = try_operator_execution(
        user_text="check Vercel deploy Workspace: /tmp",
        gctx=gctx,
        db=db_session,
        snapshot={},
    )
    assert r.handled is False


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_operator_loop_handles_vercel_cue(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_execution_loop.get_settings",
        lambda: __import__("types").SimpleNamespace(nexa_operator_mode=True),
    )
    monkeypatch.setattr(
        "app.services.operator_runners.vercel.run_vercel_operator_readonly",
        lambda cwd=None: (
            "### Progress\n\n→ stub\n\nvercel ok",
            {"provider": "vercel"},
            ["Starting Vercel investigation"],
            True,
        ),
    )

    uid = f"op_{uuid.uuid4().hex[:8]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    r = try_operator_execution(
        user_text="Please check my Vercel project logs",
        gctx=gctx,
        db=db_session,
        snapshot={},
    )
    assert r.handled is True
    assert r.provider == "vercel"
    assert "stub" in r.text or "vercel" in r.text.lower()


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_gateway_operator_before_execution_loop(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_execution_loop.get_settings",
        lambda: __import__("types").SimpleNamespace(nexa_operator_mode=True),
    )
    monkeypatch.setattr(
        "app.services.operator_runners.vercel.run_vercel_operator_readonly",
        lambda cwd=None: (
            "### Progress\n\n→ x\n",
            {},
            [],
            True,
        ),
    )
    calls: list[str] = []

    def boom(**kw):
        calls.append("exec_loop")
        from app.services.execution_loop import ExecutionLoopResult

        return ExecutionLoopResult(handled=False, text="")

    monkeypatch.setattr("app.services.execution_loop.try_execute_or_explain", boom)

    uid = f"op_{uuid.uuid4().hex[:8]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    out = NexaGateway().handle_message(gctx, "tail Vercel logs for my-app.vercel.app", db=db_session)
    assert out.get("operator_execution") is True
    assert calls == []
