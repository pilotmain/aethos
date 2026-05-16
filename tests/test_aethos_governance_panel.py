# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.runtime_governance import build_governance_audit


def test_governance_brain_decisions_section() -> None:
    g = build_governance_audit()
    assert "brain_routing_decisions" in g
