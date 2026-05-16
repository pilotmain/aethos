# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_identity_final import build_aethos_runtime_identity_final


def test_runtime_identity_final() -> None:
    out = build_aethos_runtime_identity_final({})
    final = out["aethos_runtime_identity_final"]
    assert final["platform"] == "AethOS"
    assert final["terminology_version"] == "phase4_step12"
