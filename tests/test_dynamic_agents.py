"""Phase 9 — user-defined agent handles in mission text."""

from __future__ import annotations

from app.services.agents.factory import create_agent
from app.services.missions.parser import parse_loose_mission
from app.services.runtime_agents.factory import create_runtime_agents


def test_create_agent_serializes_tools():
    row = create_agent("@trader", "crypto analyst", ["research", "forecast"])
    assert row["handle"] == "trader"
    assert row["role"] == "crypto analyst"
    assert row["tools"] == ["research", "forecast"]


def test_loose_mission_unknown_handle_line():
    text = "@trader: analyze BTC trend over the last quarter for volatility signals"
    mission = parse_loose_mission(text)
    assert mission is not None
    agents = mission.get("agents") or []
    assert len(agents) == 1
    assert agents[0]["role"] == "trader"
    assert "BTC" in agents[0]["task"]


def test_runtime_factory_normalizes_dynamic_handle():
    mission = parse_loose_mission(
        "@quant_bot: evaluate ETH liquidity versus BTC pairs using latest inputs"
    )
    assert mission
    agents = create_runtime_agents(mission, "user_x")
    assert agents[0]["handle"] == "quant_bot"
