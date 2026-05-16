# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.operational_freeze_lock import build_operational_freeze_lock


def test_operational_freeze_lock() -> None:
    out = build_operational_freeze_lock()
    assert out["operational_freeze_lock"]["release_candidate"] is True
    assert out["production_surface_lock"]["additive_only"] is True
