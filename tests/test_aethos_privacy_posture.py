# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.privacy_operational_posture import build_privacy_operational_posture


def test_privacy_posture_keys() -> None:
    p = build_privacy_operational_posture()
    assert "privacy_posture" in p
    assert "egress_decisions" in p
    assert "blocked_operations" in p
