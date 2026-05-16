# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.governance_search import filter_governance_entries, search_governance_entries


def test_governance_search_returns_shape() -> None:
    out = search_governance_entries("provider", limit=8)
    assert "entries" in out
    assert "total" in out


def test_governance_filter_by_kind() -> None:
    out = filter_governance_entries(kind="provider", limit=8)
    assert "entries" in out
    assert out.get("filters", {}).get("kind") == "provider"
