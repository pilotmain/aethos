"""P0 — execution loop runs before structured routing / LLM on gateway admission."""

from __future__ import annotations

import uuid

import pytest

from app.services.execution_loop import ExecutionLoopResult, try_execute_or_explain
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_try_execute_or_explain_not_handled_for_smalltalk(db_session) -> None:
    uid = f"el_{uuid.uuid4().hex[:10]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    res = try_execute_or_explain(
        user_text="hello there",
        gctx=gctx,
        db=db_session,
        snapshot={},
    )
    assert res.handled is False


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_handle_message_short_circuits_before_parse_mission(monkeypatch, db_session) -> None:
    parse_calls: list[str] = []

    def capture_parse(text: str):
        parse_calls.append(text)
        return None

    monkeypatch.setattr(
        "app.services.execution_loop.try_execute_or_explain",
        lambda **kw: ExecutionLoopResult(
            handled=True,
            text="### Progress\n\n→ Starting investigation\n\n---\n\nstub",
        ),
    )
    monkeypatch.setattr(
        "app.services.missions.parser.parse_mission",
        capture_parse,
    )

    uid = f"el_{uuid.uuid4().hex[:10]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    out = NexaGateway().handle_message(
        gctx,
        "check Railway deploy logs",
        db=db_session,
    )
    assert out.get("execution_loop") is True
    assert out.get("verified") is False
    assert parse_calls == []
