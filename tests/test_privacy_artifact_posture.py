# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.privacy_operational_posture import build_privacy_operational_posture


def test_sensitive_artifacts_key() -> None:
    assert "sensitive_artifacts" in build_privacy_operational_posture()
