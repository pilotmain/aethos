"""Unified routing authority: orchestrator/runtime suppress implicit web."""

from __future__ import annotations

from app.services.response_formatter import soften_capability_downgrade_phrases
from app.services.routing.authority import (
    RouteKind,
    build_routing_context,
    resolve_route,
    resolve_route_dict,
    should_suppress_public_web_pipeline,
)


def test_spawn_group_id_routes_orchestrator_and_suppresses_web() -> None:
    t = "status of spawn_group_id spawn_ac16ad6baaf8 what about competitors"
    ctx = build_routing_context(t)
    assert ctx["has_spawn_group_id"] is True
    assert resolve_route(ctx) == RouteKind.ORCHESTRATOR
    assert should_suppress_public_web_pipeline(t) is True


def test_boss_mention_suppresses_web() -> None:
    t = "@boss search the web for robotics news"
    ctx = build_routing_context(t)
    assert ctx["has_boss_mention"] is True
    assert resolve_route(ctx) == RouteKind.ORCHESTRATOR
    assert should_suppress_public_web_pipeline(t) is True


def test_boss_research_robots_routes_orchestrator_not_implicit_web() -> None:
    t = "@boss research robotics using agents"
    ctx = build_routing_context(t)
    assert resolve_route(ctx) == RouteKind.ORCHESTRATOR
    assert should_suppress_public_web_pipeline(t) is True


def test_resolve_route_dict_shape() -> None:
    d = resolve_route_dict("@boss bounded mission test", user_id="u1", session_id="s1")
    assert d["route"] == "orchestrator"
    assert d["confidence"] == 1.0
    assert "reason" in d


def test_ops_route_when_no_boss() -> None:
    t = "/ops status"
    ctx = build_routing_context(t)
    assert ctx.get("has_ops_intent") is True
    assert resolve_route(ctx) == RouteKind.OPS


def test_explicit_web_only_when_no_orchestration() -> None:
    t = "search the web for latest Rust release notes"
    ctx = build_routing_context(t)
    assert resolve_route(ctx) == RouteKind.WEB_SEARCH
    assert should_suppress_public_web_pipeline(t) is False


def test_runtime_intent_suppresses_web() -> None:
    t = "create a bounded agent swarm with @research-analyst to investigate X"
    ctx = build_routing_context(t)
    assert ctx["contains_runtime_intent"] is True
    assert resolve_route(ctx) == RouteKind.RUNTIME_TOOL
    assert should_suppress_public_web_pipeline(t) is True


def test_catalog_agent_mention_route() -> None:
    t = "@research compare Postgres and MySQL for OLTP"
    ctx = build_routing_context(t)
    assert ctx["has_agent_mention"] is True
    assert resolve_route(ctx) == RouteKind.AGENT


def test_soften_read_only_phrase() -> None:
    s = soften_capability_downgrade_phrases("I am read-only. Sources below.")
    assert "I am read-only" not in s
    assert "read-only web tools" in s.lower()
