# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.enterprise_operational_strategy import build_enterprise_operational_strategy


def test_enterprise_operational_strategy() -> None:
    out = build_enterprise_operational_strategy({})
    assert out.get("advisory") is True
    assert "resilience_strategy" in out
