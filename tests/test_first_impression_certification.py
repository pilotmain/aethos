# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.setup.first_impression_certification import build_first_impression_certification


def test_first_impression_certification() -> None:
    out = build_first_impression_certification()
    cert = out["first_impression_certification"]
    assert cert["certified_phase"] == "phase4_step15"
    assert "setup_clarity" in cert["areas"]
