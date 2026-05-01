"""Mission parser — strict vs loose ``parse_mission`` and gateway smoke."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models.nexa_next_runtime import NexaMission
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway
from app.services.missions.parser import parse_loose_mission, parse_mission


def test_parse_mission_strict_handles_prefixed_lines() -> None:
    text = """Mission: "Quick scan"

@researcher-pro: find robotics trends in warehouses.
@analyst-pro: write forecast mentioning @researcher-pro.

single-cycle"""
    m = parse_mission(text)
    assert m is not None
    assert "tasks" in m or "agents" in m
    steps = m.get("tasks") or m.get("agents") or []
    assert len(steps) >= 2


def test_parse_mission_loose_role_lines() -> None:
    text = """Mission: "Loose demo"

Researcher: find robotics trends
Analyst: write forecast
QA: review the draft carefully"""
    m = parse_mission(text)
    assert m is not None
    agents = m.get("agents") or []
    assert len(agents) == 3
    assert agents[1]["depends_on"]


def test_parse_loose_at_lines_without_quoted_title() -> None:
    text = """@researcher-pro: find robotics trends
@analyst-pro: write forecast"""
    m = parse_loose_mission(text)
    assert m is not None
    assert len(m["agents"]) == 2


def test_gateway_runs_loose_and_updates_state(nexa_runtime_clean) -> None:
    text = """Researcher: find robotics trends here
Analyst: write forecast summary here"""
    gw = NexaGateway()
    gctx = GatewayContext.from_channel("u_phase2", "web", {})
    out = gw.handle_message(gctx, text)
    assert out["status"] == "completed"
    n = nexa_runtime_clean.scalar(select(func.count()).select_from(NexaMission))
    assert n >= 1
