# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from app.services.setup.branding_purge import scan_user_facing_branding


def test_no_openhub_clawhub_in_cli_help() -> None:
    text = Path("aethos_cli/__main__.py").read_text(encoding="utf-8")
    for line in text.splitlines():
        if "help=" not in line:
            continue
        for term in ("OpenHub", "ClawHub", "openhub", "ClawHub"):
            assert term not in line


def test_branding_scan_reports_structure() -> None:
    out = scan_user_facing_branding()
    assert out["user_facing_brand"] == "AethOS"
    assert "allowed_openclaw" in out
