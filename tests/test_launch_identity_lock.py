# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.launch_identity_lock import build_aethos_launch_identity


def test_launch_identity_lock() -> None:
    out = build_aethos_launch_identity({})
    ident = out["aethos_launch_identity"]
    assert ident["platform"] == "AethOS"
    assert ident["launch_grade"] is True
    assert ident["terminology_version"] == "phase4_step13"
