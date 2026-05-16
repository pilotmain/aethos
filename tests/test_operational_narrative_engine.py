# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.operational_narrative_engine import build_operational_narratives_v2


def test_operational_narratives_v2() -> None:
    out = build_operational_narratives_v2({})
    assert out["operational_narratives_v2"]["bounded"] is True
    assert isinstance(out["runtime_storyline"], list)
