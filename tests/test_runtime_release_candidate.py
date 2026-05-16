# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.release_candidate_certification import build_runtime_enterprise_grade


def test_runtime_release_candidate_grade() -> None:
    out = build_runtime_enterprise_grade({"launch_ready": True})
    assert "enterprise_grade" in out["runtime_enterprise_grade"]
