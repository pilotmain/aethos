# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_timeline_hydration import (
    build_timeline_window,
    search_timeline_entries,
)


def test_timeline_window_paging() -> None:
    out = build_timeline_window(limit=8, offset=0)
    assert "timeline" in out
    assert out.get("has_more") in (True, False)
    assert len(out.get("timeline") or []) <= 8


def test_timeline_search() -> None:
    out = search_timeline_entries(None, limit=5)
    assert "entries" in out
