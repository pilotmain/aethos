# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.operator_language_guide import build_operator_language_guide


def test_operator_language_guide() -> None:
    out = build_operator_language_guide()
    assert "orchestrator" in out["operator_language_guide"]["preferred_terms"]
