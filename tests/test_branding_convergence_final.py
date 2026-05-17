# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.setup.branding_convergence_final import build_branding_convergence_final


def test_branding_convergence_final() -> None:
    out = build_branding_convergence_final()
    assert out["branding_convergence_final"]["phase"] == "phase4_step18"
