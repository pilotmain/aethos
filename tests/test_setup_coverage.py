# SPDX-License-Identifier: Apache-2.0

from app.services.setup.setup_coverage import build_setup_coverage


def test_setup_coverage() -> None:
    out = build_setup_coverage()
    assert "provider_routing" in out["setup_coverage"]["covered_systems"]
    assert out["setup_coverage"]["phase"] == "phase4_step20"
