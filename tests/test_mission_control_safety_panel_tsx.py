"""Regression: SafetyAndReadinessPanel must bind `d` before JSX uses `d.*` (avoid ReferenceError)."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PANEL = _REPO_ROOT / "web" / "components" / "mission-control" / "SafetyAndReadinessPanel.tsx"


def test_safety_and_readiness_panel_binds_d_alias() -> None:
    text = _PANEL.read_text(encoding="utf-8")
    assert "const d = data as SafetyReadiness" in text
