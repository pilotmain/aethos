# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.runtime_governance import build_governance_timeline


def test_governance_timeline_kinds() -> None:
    g = build_governance_timeline(limit=16)
    kinds = {e.get("kind") for e in g.get("timeline") or []}
    allowed = {
        "plugin",
        "provider",
        "brain",
        "repair",
        "privacy",
        "deployment",
        "automation_pack",
        "deliverable",
        "continuation",
        "governance",
    }
    assert kinds <= allowed or not kinds
    for row in g.get("timeline") or []:
        assert row.get("what")
        assert len(str(row.get("what"))) < 500
