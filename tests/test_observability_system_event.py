"""Phase 28 — structured system event helper."""

from __future__ import annotations

from app.services.observability.system_events import log_system_event


def test_log_system_event_runs() -> None:
    log_system_event("pytest.smoke", {"x": 1})
