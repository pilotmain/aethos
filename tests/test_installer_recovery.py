# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.setup.installer_recovery_flow import build_installer_recovery_flow


def test_installer_recovery() -> None:
    out = build_installer_recovery_flow()
    assert "retry" in out["installer_recovery_flow"]["provider_failure_copy"].lower()
    assert out["installer_recovery_flow"]["resume_command"] == "aethos setup resume"
