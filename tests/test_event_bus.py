"""Phase 6 — in-process event bus records mission and task lifecycle."""

from __future__ import annotations

from app.services.events.bus import clear_events, list_events
from app.services.gateway.runtime import NexaGateway


def test_events_recorded_during_mission(nexa_runtime_clean) -> None:
    clear_events()
    text = """Researcher: find robotics event bus proof here"""
    NexaGateway().handle_message(text, "u_ev")
    ev = list_events()
    types = [e.get("type") for e in ev]
    assert "mission.started" in types
    assert "task.started" in types
    assert "artifact.created" in types
    assert "task.completed" in types
    assert "mission.completed" in types
