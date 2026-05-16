# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.enterprise_operator_trust import build_enterprise_operator_trust


def test_enterprise_operator_trust() -> None:
    out = build_enterprise_operator_trust({})
    assert "connection_unavailable" in out["operational_messages"]
    assert "AethOS" in out["operational_messages"]["connection_unavailable"]
