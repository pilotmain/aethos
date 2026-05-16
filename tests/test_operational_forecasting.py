# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.operational_forecasting import build_operational_forecasting


def test_operational_forecasting_advisory() -> None:
    out = build_operational_forecasting({})
    assert out.get("advisory") is True
    assert out.get("runtime_derived") is True
