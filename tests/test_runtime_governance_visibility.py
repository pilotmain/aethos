# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.runtime_governance import build_governance_audit


def test_governance_summary_humanized() -> None:
    g = build_governance_audit()
    assert "summary" in g
    assert "brain_routing_decisions" in g
