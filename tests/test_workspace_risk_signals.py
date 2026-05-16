# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.workspace_runtime_intelligence import build_operational_risk, build_workspace_intelligence


def test_risk_signals_list() -> None:
    wi = build_workspace_intelligence()
    assert isinstance(wi.get("risk_signals"), list)


def test_operational_risk_high_risk_key() -> None:
    risk = build_operational_risk()
    assert "high_risk_projects" in risk
