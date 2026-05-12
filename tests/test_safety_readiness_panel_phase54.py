# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from pathlib import Path


def test_safety_panel_component_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    p = root / "web" / "components" / "mission-control" / "SafetyAndReadinessPanel.tsx"
    txt = p.read_text(encoding="utf-8")
    assert "SafetyAndReadinessPanel" in txt
    assert "sandbox_mode" in txt
