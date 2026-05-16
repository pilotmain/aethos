# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.privacy_operational_posture import build_privacy_operational_posture


def test_egress_decisions_shape() -> None:
    e = build_privacy_operational_posture().get("egress_decisions") or {}
    assert "allowed" in e
    assert "blocked" in e
