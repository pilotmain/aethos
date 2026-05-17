# SPDX-License-Identifier: Apache-2.0

from pathlib import Path


def test_install_scripts_say_aethos() -> None:
    root = Path(__file__).resolve().parents[1]
    install = (root / "install.sh").read_text(encoding="utf-8")
    setup_sh = (root / "scripts" / "setup.sh").read_text(encoding="utf-8")
    assert "AethOS" in install
    assert "Enterprise Setup" in setup_sh
    assert "OpenClaw" not in setup_sh
