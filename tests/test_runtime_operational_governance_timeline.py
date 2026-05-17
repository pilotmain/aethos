# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_operational_governance_timeline import build_runtime_operational_governance_timeline


def test_governance_timeline_bounded() -> None:
    blob = build_runtime_operational_governance_timeline({})
    tl = blob["runtime_operational_governance_timeline"]
    assert tl["bounded"] is True
    assert len(tl["events"]) <= 32
