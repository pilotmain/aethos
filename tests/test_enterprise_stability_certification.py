# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.enterprise_stability_certification import build_enterprise_stability_certification


def test_enterprise_stability_certification() -> None:
    out = build_enterprise_stability_certification({})
    cert = out["enterprise_stability_certification"]
    assert cert["certified"] is True
    assert cert["validated_systems"]
