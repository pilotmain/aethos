# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.strategic_forecast_optimization import build_adaptive_operational_forecasting


def test_adaptive_operational_forecasting() -> None:
    out = build_adaptive_operational_forecasting({})
    assert out.get("advisory") is True
    assert "runtime_prediction_confidence" in out
