"""P0 — hosted Railway URLs must not spawn parse_mission / fake https agents."""

from __future__ import annotations

import uuid

import pytest

from app.services.execution_loop import ExecutionLoopResult
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_hosted_railway_url_short_circuits_before_parse_mission(monkeypatch, db_session) -> None:
    parse_calls: list[str] = []

    def capture_parse(text: str):
        parse_calls.append(text)
        return None

    monkeypatch.setattr(
        "app.services.execution_loop.try_execute_or_explain",
        lambda **kw: ExecutionLoopResult(
            handled=True,
            text="### Progress\n\n→ Starting investigation\n\nstub",
        ),
    )
    monkeypatch.setattr(
        "app.services.missions.parser.parse_mission",
        capture_parse,
    )

    uid = f"el_{uuid.uuid4().hex[:10]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    NexaGateway().handle_message(
        gctx,
        "https://railway.com/project/abc/service — deploy failing",
        db=db_session,
    )
    assert parse_calls == []
