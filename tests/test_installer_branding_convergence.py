# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.setup.setup_branding_convergence import build_setup_branding_convergence


def test_installer_branding_convergence() -> None:
    out = build_setup_branding_convergence()
    assert out["setup_branding_convergence"]["user_facing_brand"] == "AethOS"
