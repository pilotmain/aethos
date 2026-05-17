# SPDX-License-Identifier: Apache-2.0

from app.services.setup.production_cut_certification import build_production_cut_certification


def test_production_cut_certification() -> None:
    out = build_production_cut_certification(truth={"runtime_resilience": {}, "hydration_progress": {}, "runtime_process_supervision": {}})
    cert = out["production_cut_certification"]
    assert "enterprise_grade" in cert
    assert "production_cut_ready" in cert
    assert cert["phase"] == "phase4_step20"
