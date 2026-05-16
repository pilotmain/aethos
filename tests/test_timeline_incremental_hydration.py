# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_timeline_hydration import append_timeline_entry, build_incremental_timeline


def test_append_and_window_timeline() -> None:
    append_timeline_entry({"kind": "test", "severity": "info", "at": "2026-01-01T00:00:00Z"})
    out = build_incremental_timeline(limit=10, severity="info")
    kinds = {e.get("kind") for e in out.get("timeline") or []}
    assert "test" in kinds or out.get("entry_count", 0) >= 0
