# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from aethos_cli.setup_ready_state_semantics import build_setup_completion_card, evaluate_setup_readiness


def test_not_ready_when_api_offline() -> None:
    health = {
        "checks": [
            {"name": "api_health", "ok": False, "detail": "offline"},
            {"name": "mission_control", "ok": False, "detail": "offline"},
        ],
        "all_critical_ok": True,
    }
    state = evaluate_setup_readiness(health=health)
    assert state["may_claim_ready"] is False
    title, lines = build_setup_completion_card(health=health, api_base="http://127.0.0.1:8010", bag={})
    assert title == "Configuration complete"
    assert any("not running yet" in line.lower() for line in lines)


def test_ready_when_api_and_mc_up() -> None:
    health = {
        "checks": [
            {"name": "api_health", "ok": True, "detail": "HTTP 200"},
            {"name": "mission_control", "ok": True, "detail": "HTTP 200"},
        ],
        "all_critical_ok": True,
    }
    title, lines = build_setup_completion_card(
        health=health,
        api_base="http://127.0.0.1:8010",
        bag={"routing_summary": "Hybrid"},
        truly_operational=True,
    )
    assert title == "AethOS is running"
    assert any("Mission Control is ready" in line for line in lines)
