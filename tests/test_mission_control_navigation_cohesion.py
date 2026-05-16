# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from pathlib import Path

_PRIMARY = (
    "Office",
    "Runtime",
    "Deployments",
    "Providers",
    "Marketplace",
    "Privacy",
    "Governance",
    "Settings",
)


def test_primary_nav_matches_phase3_step4() -> None:
    nav = (Path(__file__).resolve().parents[1] / "web/lib/navigation.ts").read_text()
    for label in _PRIMARY:
        assert f'name: "{label}"' in nav, f"missing primary nav item {label}"
    assert 'href: "/mission-control/office"' in nav
    assert 'href: "/mission-control/marketplace"' in nav
    assert "deprecated: true" in nav
    assert "CEO (legacy)" in nav
