from __future__ import annotations

from pathlib import Path


def test_nexa_doctor_script_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    p = root / "scripts" / "nexa_doctor.sh"
    assert p.is_file()
    txt = p.read_text(encoding="utf-8")
    assert "install_check.sh" in txt
