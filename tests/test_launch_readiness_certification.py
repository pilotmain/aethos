# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.launch_readiness_certification import build_launch_readiness_certification


def test_launch_readiness_certification() -> None:
    cert = build_launch_readiness_certification()
    assert cert["launch_ready"] is True
    assert cert["certified_phase"] == "phase4_step13"
    assert cert["verified_suites"]
