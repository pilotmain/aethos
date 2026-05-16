# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.privacy_operational_posture import build_privacy_operational_posture


def test_workflow_posture_list() -> None:
    p = build_privacy_operational_posture()
    assert "workflow_posture" in p
    assert isinstance(p["workflow_posture"], list)
