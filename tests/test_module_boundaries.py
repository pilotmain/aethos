"""Phase 15 — canonical locations for providers, plugins, and channels."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_boundary_directories_exist() -> None:
    assert (ROOT / "app/services/providers").is_dir()
    assert (ROOT / "app/plugins").is_dir()
    assert (ROOT / "app/services/channels").is_dir()
