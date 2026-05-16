# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.ecosystem_operational_strategy import build_ecosystem_operational_strategy


def test_ecosystem_operational_strategy() -> None:
    out = build_ecosystem_operational_strategy({})
    assert out.get("advisory") is True
