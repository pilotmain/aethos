"""Mission Control execution state includes privacy + provider event streams."""

from __future__ import annotations

from app.services.mission_control.nexa_next_state import (
    STATE,
    add_privacy_event,
    add_provider_event,
    build_execution_snapshot,
)


def test_execution_snapshot_includes_privacy_and_provider_streams(db_session) -> None:
    STATE["privacy_events"].clear()
    STATE["provider_events"].clear()

    add_privacy_event({"type": "pii_redacted", "data": {"pii": ["email"]}})
    add_provider_event({"provider": "local_stub", "agent": "researcher", "status": "completed"})

    s = build_execution_snapshot(db_session)
    assert "privacy_events" in s and s["privacy_events"]
    assert "provider_events" in s and s["provider_events"]
    assert s["privacy_events"][0]["type"] == "pii_redacted"
    assert s["provider_events"][0]["provider"] == "local_stub"
