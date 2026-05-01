"""Phase 43 — autonomous planner and optional long-running gateway ticks."""

from __future__ import annotations

import uuid

from app.core.config import get_settings
from app.services.agents.long_running import tick_eligible_db_sessions, upsert_db_session
from app.services.autonomy.planner import autonomous_planner
from app.services.events.bus import clear_events, list_events
from app.services.gateway.runtime import NexaGateway


def test_autonomous_planner_skipped_when_mode_off() -> None:
    out = autonomous_planner()
    assert out.get("skipped") is True


def test_autonomous_planner_emits_event(monkeypatch) -> None:
    monkeypatch.setenv("NEXA_AUTONOMOUS_MODE", "true")
    get_settings.cache_clear()
    clear_events()
    try:
        out = autonomous_planner()
        assert out.get("ok") is True
        assert out.get("task_id")
        ev = list_events()[-1]
        assert ev["type"] == "autonomous.planner.tick"
        assert ev.get("task_id") == out.get("task_id")
    finally:
        monkeypatch.delenv("NEXA_AUTONOMOUS_MODE", raising=False)
        get_settings.cache_clear()


def test_long_running_tick_calls_gateway_when_flags(monkeypatch, db_session) -> None:
    monkeypatch.setenv("NEXA_AUTONOMOUS_MODE", "true")
    monkeypatch.setenv("NEXA_LONG_RUNNING_GATEWAY_TICK", "true")
    get_settings.cache_clear()
    calls: list[tuple[str, str]] = []

    def fake_handle(self, gctx, text: str, db=None):
        calls.append((gctx.channel, (text or "")))
        return {"mode": "chat", "text": "ok"}

    monkeypatch.setattr(NexaGateway, "handle_message", fake_handle)
    try:
        uid = f"lr_gw_{uuid.uuid4().hex[:10]}"
        goal_token = f"phase43_tick_{uuid.uuid4().hex}"
        upsert_db_session(
            db_session,
            user_id=uid,
            session_key=f"sk_{uuid.uuid4().hex[:8]}",
            goal=goal_token,
            interval_seconds=30,
        )
        tick_eligible_db_sessions(db_session)
        ours = [c for c in calls if goal_token in c[1]]
        assert len(ours) == 1
        assert ours[0][0] == "long_running"
    finally:
        monkeypatch.delenv("NEXA_AUTONOMOUS_MODE", raising=False)
        monkeypatch.delenv("NEXA_LONG_RUNNING_GATEWAY_TICK", raising=False)
        get_settings.cache_clear()
