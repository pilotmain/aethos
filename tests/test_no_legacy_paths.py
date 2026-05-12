# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 15 — legacy helpers and duplicate routes stay removed."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_deprecated_mission_ws_helper_removed() -> None:
    assert not (ROOT / "web/lib/ws/reconnectingMissionWs.ts").exists()


def test_build_mission_control_runtime_state_removed() -> None:
    src = (ROOT / "app/services/mission_control/nexa_next_state.py").read_text(encoding="utf-8")
    assert "build_mission_control_runtime_state" not in src


def test_duplicate_events_stream_route_removed() -> None:
    routes = (ROOT / "app/api/routes/mission_control.py").read_text(encoding="utf-8")
    assert "/events/stream" not in routes
