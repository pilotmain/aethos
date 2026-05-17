# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_governance_authority import build_runtime_governance_authority


def test_runtime_supervision_authority() -> None:
    gov = build_runtime_governance_authority({})
    assert gov["runtime_governance_discipline"]["orchestrator_owned"] is True
