# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.runtime.events.runtime_events import emit_runtime_event
from app.runtime.runtime_state import load_runtime_state
from app.services.events.bus import clear_events, list_events


def test_runtime_event_publishes_to_bus_for_streaming(api_client, tmp_path, monkeypatch) -> None:
    """WebSocket handler subscribes to the same bus — verify publish shape (no async race)."""
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    clear_events()
    _, uid = api_client
    st = load_runtime_state()
    emit_runtime_event(st, "task_created", task_id="tw", user_id=uid, status="queued")
    evs = list_events()
    assert any(
        isinstance(e, dict) and e.get("type") == "runtime.task_created" and (e.get("payload") or {}).get("user_id") == uid
        for e in evs
    )
