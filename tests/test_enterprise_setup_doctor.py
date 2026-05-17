# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.setup.enterprise_setup_doctor import build_enterprise_setup_doctor


def test_enterprise_setup_doctor() -> None:
    out = build_enterprise_setup_doctor()
    doc = out["enterprise_setup_doctor"]
    assert doc["phase"] == "phase4_step20"
    assert doc["checks"]
