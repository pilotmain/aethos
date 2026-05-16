# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_event_intelligence import events_for_ws_replay


def test_ws_replay_tail() -> None:
    rows = events_for_ws_replay(limit=5)
    assert isinstance(rows, list)
