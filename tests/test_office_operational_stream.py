# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.office_operational_stream import build_office_operational_stream


def test_office_stream_staggered() -> None:
    out = build_office_operational_stream({})
    assert out["silent_background_refresh"] is True
    assert out["staggered_refresh_ms"]["workers"] > 0
