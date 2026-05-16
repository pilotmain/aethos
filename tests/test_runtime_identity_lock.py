# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_identity_lock import build_runtime_identity_lock


def test_identity_lock_aethos_brand() -> None:
    out = build_runtime_identity_lock({})
    assert out["runtime_identity_lock"]["user_facing_brand"] == "AethOS"
    assert out["runtime_identity_lock"]["locked"] is True
