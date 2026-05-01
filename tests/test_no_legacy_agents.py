"""Phase 26 — legacy static persona chips must not ship in Nexa-Next UI."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_workspace_app_has_no_legacy_persona_strings() -> None:
    text = (ROOT / "web/components/nexa/WorkspaceApp.tsx").read_text(encoding="utf-8")
    banned = ("@dev ", "@ops ", "@strategy ", "@research ", "@reset ")
    for b in banned:
        assert b not in text, f"legacy chip insert {b!r} must be removed"
