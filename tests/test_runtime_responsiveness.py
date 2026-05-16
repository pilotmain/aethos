# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_hydration import build_incremental_timeline, get_lightweight_slice


def test_lightweight_timeline_is_bounded() -> None:
    tl = build_incremental_timeline(limit=20)
    assert tl.get("incremental") is True
    assert len(tl.get("timeline") or []) <= 48


def test_lightweight_workers_slice_shape() -> None:
    sl = get_lightweight_slice("workers", None)
    assert isinstance(sl, dict)
