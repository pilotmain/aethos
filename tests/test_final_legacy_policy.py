# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.final_legacy_policy import build_final_legacy_policy


def test_final_legacy_policy() -> None:
    out = build_final_legacy_policy()
    assert out["final_legacy_policy"]["user_facing_brand"] == "AethOS"
    assert "NEXA_*" in str(out["final_legacy_policy"]["nexa_allowed"])
