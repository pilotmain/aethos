# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_governance_consolidation import build_runtime_governance_consolidation


def test_runtime_governance_consolidation() -> None:
    blob = build_runtime_governance_consolidation({})
    assert "enterprise_runtime_governance_final" in blob
