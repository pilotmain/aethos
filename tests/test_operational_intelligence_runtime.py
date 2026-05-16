# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.operational_intelligence import build_operational_intelligence


def test_operational_intelligence_shape() -> None:
    out = build_operational_intelligence({"queued_tasks": 0, "reliability": {}})
    assert "insights" in out
    assert isinstance(out["insights"], list)
