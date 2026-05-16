# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.release_candidate_certification import build_release_candidate_certification


def test_release_candidate_certification() -> None:
    out = build_release_candidate_certification({"launch_ready": True})
    cert = out["release_candidate_certification"]
    assert cert["certified_phase"] == "phase4_step14"
    assert cert["release_candidate"] is True
