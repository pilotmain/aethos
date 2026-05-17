# SPDX-License-Identifier: Apache-2.0

from app.services.setup.final_branding_convergence_audit import build_final_branding_convergence_audit


def test_final_branding_convergence_audit_shape() -> None:
    out = build_final_branding_convergence_audit()
    audit = out["final_branding_convergence_audit"]
    assert "operator_visible_legacy_refs" in audit
    assert "by_classification" in audit
    assert audit.get("phase") == "phase4_step21"
