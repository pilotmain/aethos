# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from app.services.setup.ui_branding_purge_final import scan_ui_branding_final


def test_active_work_panel_aethos_branded() -> None:
    text = Path("web/components/mission-control/ActiveWorkPanel.tsx").read_text(encoding="utf-8")
    assert "What AethOS is doing" in text
    assert "What Nexa is doing" not in text


def test_ui_branding_scan_structure() -> None:
    out = scan_ui_branding_final()
    assert out["phase"] == "phase4_step19"
    assert "nexa_ui_violations" in out
