# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 15 — runtime events carry the locked envelope fields."""

from __future__ import annotations

import pytest

from app.services.events.bus import clear_events, list_events, publish
from app.services.events.envelope import emit_runtime_event


def test_emit_runtime_event_locked_keys() -> None:
    clear_events()
    emit_runtime_event(
        "task.started",
        mission_id="m-1",
        agent="alpha",
        user_id="u1",
        payload={"step": 1},
    )
    ev = list_events()[-1]
    assert ev["type"] == "task.started"
    assert ev["mission_id"] == "m-1"
    assert ev["agent"] == "alpha"
    assert ev["user_id"] == "u1"
    assert isinstance(ev["timestamp"], str) and ev["timestamp"]
    assert ev["payload"] == {"step": 1}


def test_publish_normalizes_minimal_event() -> None:
    clear_events()
    publish({"type": "minimal.probe"})
    ev = list_events()[-1]
    assert set(ev.keys()) >= {"type", "timestamp", "mission_id", "agent", "payload"}
    assert ev["mission_id"] is None
    assert ev["agent"] is None
    assert ev["payload"] == {}


def test_publish_coerces_non_dict_payload() -> None:
    clear_events()
    publish({"type": "raw.payload", "payload": "hello"})
    assert list_events()[-1]["payload"] == {"value": "hello"}


def test_publish_rejects_missing_or_blank_type() -> None:
    clear_events()
    with pytest.raises(ValueError):
        publish({})
    with pytest.raises(ValueError):
        publish({"type": ""})
