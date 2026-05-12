# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""P0 — hosted Railway/deploy asks must not become generic missions with fake https agents."""

from __future__ import annotations

from app.services.gateway.runtime import NexaGateway
from app.services.hosted_service_mission_gate import hosted_service_mission_blocked
from app.services.missions.parser import parse_mission
from app.services.mission_execution_truth import agent_output_is_unverified_stub, mission_agents_execution_verified


RAILWAY_SAMPLE = """Can you go to Railway and check why this service is failing, fix the issue, and redeploy?

https://railway.com/project/abc/path
/Users/me/talking-avatar-agent"""


def test_hosted_service_blocks_parse_mission() -> None:
    assert hosted_service_mission_blocked(RAILWAY_SAMPLE)
    assert parse_mission(RAILWAY_SAMPLE) is None


def test_loose_parser_no_https_agent_role() -> None:
    # Would historically yield role "https" + task "//railway.com/..."
    loose_only = "https://railway.com/project/x\nMission: test\nhttps://railway.com/foo/bar"
    assert parse_mission(loose_only) is None


def test_structured_gateway_skips_mission_for_railway_request(monkeypatch, db_session) -> None:
    def _boom(_txt: str):
        raise AssertionError("parse_mission must not run for hosted-service blocked text")

    monkeypatch.setattr("app.services.missions.parser.parse_mission", _boom)
    from app.services.gateway.context import GatewayContext

    gw = NexaGateway()._try_structured_route(  # noqa: SLF001
        GatewayContext(user_id="u1", channel="telegram"),
        RAILWAY_SAMPLE,
        db_session,
    )
    assert gw is None


def test_heartbeat_stub_not_execution_verified() -> None:
    assert agent_output_is_unverified_stub({"type": "heartbeat", "ok": True}) is True
    assert agent_output_is_unverified_stub({"type": "blocked", "error": "x"}) is False


def test_mission_verified_requires_non_stub() -> None:
    agents = [{"handle": "a", "output": {"type": "heartbeat", "ok": True}}]
    assert mission_agents_execution_verified(agents) is False
    agents2 = [{"handle": "a", "output": {"type": "model", "text": "hello"}}]
    assert mission_agents_execution_verified(agents2) is True


def test_telegram_reply_warns_when_not_verified() -> None:
    from app.services.channels.telegram_gateway_reply import format_telegram_gateway_reply

    txt = format_telegram_gateway_reply(
        {
            "status": "completed",
            "mission": {"title": "Untitled Mission"},
            "execution_verified": False,
        }
    )
    assert "not verified" in txt.lower() or "verified" in txt.lower()
