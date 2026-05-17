# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_governance_authority import build_runtime_governance_authority


def test_runtime_governance_cycles() -> None:
    assert build_runtime_governance_authority({})["runtime_governance_authority"]["phase"] == "phase4_step26"
