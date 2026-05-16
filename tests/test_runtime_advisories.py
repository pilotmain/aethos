# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_advisories import build_runtime_advisory_engine


def test_runtime_advisories_pressure() -> None:
    out = build_runtime_advisory_engine({"operational_pressure": {"level": "high"}})
    assert len(out["strategic_recommendations"]) >= 1
    assert out["strategic_recommendations"][0]["advisory_only"] is True
