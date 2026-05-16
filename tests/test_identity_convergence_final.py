# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.identity_convergence_audit import build_identity_convergence_audit


def test_identity_convergence_final() -> None:
    out = build_identity_convergence_audit()
    audit = out["identity_convergence_audit"]
    assert audit["user_facing_brand"] == "AethOS"
    assert audit["phase"] == "phase4_step14"
