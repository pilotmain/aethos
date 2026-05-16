# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.mission_control.operator_productivity import build_enterprise_productivity_signals


def test_operational_productivity_signals() -> None:
    out = build_enterprise_productivity_signals({"runtime_identity": {}})
    assert "operator_productivity_metrics" in out
    assert out["operational_acceleration"].get("incremental_hydration") is True
