# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.agent_registry import resolve_mention_key
from app.services.agent_router import parse_leading_mention, route_agent
from app.services.mention_control import parse_mention


def test_route_agent_dev_and_aethos():
    assert route_agent("ask cursor to fix the tests")["agent_key"] == "developer"
    assert route_agent("I feel totally overwhelmed with tasks")["agent_key"] == "aethos"
    r = route_agent("random hello")
    assert r["agent_key"] == "aethos"
    assert float(r["confidence"]) <= 0.6


def test_explicit_mention_parsing():
    r = route_agent("@dev fix the worker", context_snapshot={})
    assert r["agent_key"] == "developer"
    assert r.get("routed_text") and "fix" in str(r.get("routed_text"))
    assert route_agent("@qa review pytest")["agent_key"] == "qa"


def test_parse_mention() -> None:
    a, b = parse_leading_mention("@dev fix the tests now")
    assert a == "developer"
    assert "fix" in b
    p = parse_mention("@dev fix the tests now")
    assert p.agent_key == "dev" and p.text == "fix the tests now"


def test_resolve_mention_key():
    assert resolve_mention_key("reset") == "aethos"
    assert resolve_mention_key("developer") == "developer"
