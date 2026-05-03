"""Phase 53 — install_check.sh present and safe."""

from __future__ import annotations

from pathlib import Path


def test_install_check_script_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "install_check.sh"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "install_check" in text
    assert "rm -rf /" not in text
