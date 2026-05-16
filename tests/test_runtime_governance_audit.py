# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.runtime_governance import build_governance_audit


def test_governance_audit_sections() -> None:
    out = build_governance_audit()
    assert "plugin_installs" in out
    assert "provider_operations" in out
    assert "privacy_enforcement" in out
