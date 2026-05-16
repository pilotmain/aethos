# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.enterprise_operational_overview import build_executive_operational_overview


def test_executive_operational_overview() -> None:
    out = build_executive_operational_overview(
        {"enterprise_runtime_summaries": {"operational_summary": {"health": "healthy"}}}
    )
    assert out["summary_first"] is True
    assert "executive_operational_overview" in out
