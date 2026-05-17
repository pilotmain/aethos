# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.runtime.runtime_startup_orchestration import _START_OPTIONS


def test_start_now_options_match_spec() -> None:
    keys = [o[0] for o in _START_OPTIONS]
    assert "api_and_mission_control" in keys
    assert "api_only" in keys
    assert "save_only" in keys
    assert "review" in keys
