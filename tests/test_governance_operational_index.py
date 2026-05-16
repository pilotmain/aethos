# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.governance_operational_index import build_governance_operational_index


def test_governance_index_health() -> None:
    out = build_governance_operational_index(
        {"unified_operational_timeline": {"entry_count": 10, "entries": []}}
    )
    assert out["governance_index_health"]["healthy"] is True
