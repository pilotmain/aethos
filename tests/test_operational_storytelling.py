# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.operational_storytelling_final import build_operational_storytelling_final


def test_operational_storytelling_final() -> None:
    out = build_operational_storytelling_final({"operational_summary": {"health": "nominal"}})
    story = out["operational_storytelling_final"]
    assert "AethOS" in story["headline"]
    assert story["what_aethos_is_doing"]
